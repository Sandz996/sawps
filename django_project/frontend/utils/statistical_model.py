import logging
import traceback
import os
import time
import csv
import subprocess
import requests
from uuid import uuid4
from django.core.cache import cache
from django.utils.text import slugify
from core.settings.utils import absolute_path
from species.models import Taxon
from frontend.models.statistical import StatisticalModel
from frontend.utils.process import (
    write_pidfile,
    kill_process_by_pid
)


logger = logging.getLogger(__name__)
PLUMBER_PORT = os.getenv('PLUMBER_PORT', 8181)


def plumber_health_check(max_retry=5):
    """
    Check whether API is up and running.

    This will be called from worker.
    :param max_retry: maximum retry of checking
    :return: True if successful number of check is less than max_retry
    """
    request_url = f'http://0.0.0.0:{PLUMBER_PORT}/statistical/echo'
    retry = 0
    req = None
    time.sleep(1)
    while (req is None or req.status_code != 200) and retry < max_retry:
        try:
            req = requests.get(request_url)
            if req.status_code != 200:
                time.sleep(1)
            else:
                break
        except Exception as ex:  # noqa
            logger.error(ex)
            time.sleep(1)
        retry += 1
    if retry < max_retry:
        logger.info('Plumber API is up and running!')
    return retry < max_retry


def spawn_r_plumber():
    """Run a Plumber API server."""
    command_list = (
        [
            'R',
            '-e',
            (
                "pr <- plumber::plumb("
                f"'/home/web/plumber_data/plumber.R'); "
                f"args <- list(host = '0.0.0.0', port = {PLUMBER_PORT}); "
                "do.call(pr$run, args)"
            )
        ]
    )
    logger.info('Starting plumber API')
    process = None
    try:
        # redirect stdout and stderr
        with open('/proc/1/fd/1', 'w') as fd:
            process = subprocess.Popen(
                command_list,
                stdout=fd,
                stderr=fd
            )
        # sleep for 2 seconds to wait the API is up
        time.sleep(2)
        # we can also use polling to echo endpoint for health check
        plumber_health_check()
        # write process pid to /tmp/
        write_pidfile(process.pid, '/tmp/plumber.pid')
    except Exception as ex:  # noqa
        logger.error(ex)
        logger.error(traceback.format_exc())
        if process:
            process.terminate()
            process = None
    return process


def kill_r_plumber_process():
    """Kill plumber process by PID stored in file."""
    pid_path = os.path.join(
        '/',
        'tmp',
        'plumber.pid'
    )
    kill_process_by_pid(pid_path)


def execute_statistical_model(data_filepath, taxon: Taxon,
                              model: StatisticalModel = None):
    """
    Execute R model from exported data.

    :param data_filepath: file path of exported csv
    :param taxon: species
    :param model: optional model to be executed, \
            if model=None, then generic one will be used
    :return: tuple of is_success, json response
    """
    api_name = f'api_{model.id}' if model else 'generic'
    request_url = f'http://plumber:{PLUMBER_PORT}/statistical/{api_name}'
    data = {
        'filepath': data_filepath,
        'taxon_name': taxon.scientific_name
    }
    response = requests.post(request_url, data=data)
    content_type = response.headers['Content-Type']
    if content_type == 'application/json':
        if response.status_code == 200:
            return True, response.json()
        else:
            logger.error(
                f'Plumber error response: {str(response.json())}')
    else:
        logger.error(f'Invalid response content type: {content_type}')
    return False, None


def write_plumber_file(file_path = None):
    """Write R codes to plumber.R"""
    r_file_path = file_path if file_path else os.path.join(
        '/home/web/plumber_data',
        'plumber.R'
    )
    template_file = absolute_path(
        'frontend', 'utils', 'plumber_template.R'
    )
    with open(template_file, 'r') as f:
        lines = f.readlines()
    # fetch statistical model by species
    models = StatisticalModel.objects.all()
    for model in models:
        lines.append('\n')
        if model.taxon:
            lines.append(
                f'#* Model for species {model.taxon.scientific_name}\n')
            lines.append(f'#* @post /statistical/api_{str(model.id)}\n')
        else:
            lines.append('#* Generic Model\n')
            lines.append('#* @post /statistical/generic\n')

        lines.append('function(filepath, taxon_name) {\n')
        lines.append('  all_data <- read.csv(filepath)\n')
        lines.append('  metadata <- list(species=taxon_name)\n')
        code_lines = model.code.splitlines()
        for code in code_lines:
            lines.append(f'  {code}\n')
        lines.append('}\n')
    with open(r_file_path, 'w') as f:
        for line in lines:
            f.write(line)
    return r_file_path


def write_plumber_data(headers, csv_data):
    """
    Write csv data to file in plumber_data.

    :param headers: list of header name
    :param csv_data: list of row
    :return: file path of exported csv
    """
    r_data_path = os.path.join(
        '/home/web/plumber_data',
        f'{str(uuid4())}.csv'
    )
    with open(r_data_path, 'w', encoding='UTF8') as f:
        writer = csv.writer(f)
        # write the header
        writer.writerow(headers)
        writer.writerows(csv_data)
    return r_data_path


def remove_plumber_data(data_filepath):
    """
    Remove csv data file.

    :param data_filepath: filepath to the csv file
    """
    try:
        if os.path.exists(data_filepath):
            os.remove(data_filepath)
    except Exception as ex:
        logger.error(ex)


def get_statistical_model_output_cache_key(taxon: Taxon, output_type: str,
                                           add_key: str = None):
    """
    Build cache key for statistical model output.

    :param taxon: species
    :param output_type: model output type, e.g. NATIONAL_TREND
    :param add_key: (Optional) additional cache key \
        like Province name or Property Name
    :return: cache key
    """
    cache_key = (
        f"species-{str(taxon.id)}-{output_type.replace('_', '-')}"
    )
    if add_key:
        cache_key = cache_key + f'-{slugify(add_key)}'
    return cache_key


def save_statistical_model_output_cache(taxon: Taxon, output_type: str,
                                        json_data,
                                        add_key: str = None):
    """
    Save output of statistical model to cache.

    :param taxon: species
    :param output_type: model output type, e.g. NATIONAL_TREND
    :param json_data: json data of model output
    :param add_key: (Optional) additional cache key \
        like Province name or Property Name
    """
    cache_key = get_statistical_model_output_cache_key(taxon, output_type,
                                                       add_key=add_key)
    redis_time_cache = 21600  # 6 hours
    cache.set(cache_key, json_data, redis_time_cache)


def get_statistical_model_output_cache(taxon: Taxon, output_type: str,
                                       add_key: str = None):
    """
    Retrieve output of statistical model from cache.

    :param taxon: species
    :param output_type: model output type, e.g. NATIONAL_TREND
    :param add_key: (Optional) additional cache key \
        like Province name or Property Name
    :return: json data or None if there is no cache
    """
    cache_key = get_statistical_model_output_cache_key(taxon, output_type,
                                                       add_key=add_key)
    return cache.get(cache_key)


def clear_statistical_model_output_cache(taxon: Taxon):
    """
    Clear all output from species in the cache.

    :param taxon: species
    """
    if taxon:
        keys_pattern = f'*species-{str(taxon.id)}-*'
    else:
        # updated generic model, all cache can be cleared
        keys_pattern = '*species-*'
    output_caches = (
        cache._cache.get_client().keys(keys_pattern)
    )
    if output_caches:
        for cache_key in output_caches:
            cleaned_key = str(cache_key).split(':')[-1].replace('\'', '')
            cache.delete(cleaned_key)
