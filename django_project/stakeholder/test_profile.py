from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from stakeholder.models import (
    UserProfile
)
from sawps.tests.models.account_factory import UserF
from stakeholder.factories import (
    userProfileFactory,
    userTitleFactory,
    userRoleTypeFactory
)
from django_otp.plugins.otp_totp.models import TOTPDevice


class TestProfileView(TestCase):
    """Tests CURD on Profile Model
    and test update profile view."""

    def setUp(self):
        self.client = Client()
        # Create a test user
        self.test_user = get_user_model().objects.create_user(
            username='testuser', password='testpassword'
        )

    def test_profile_create(self):
        """
        Tests profile creation
        """
        user = UserF.create()
        profile = userProfileFactory.create(
            user=user,
            picture='profile_pictures/picture_P.jpg',
        )

        self.assertTrue(profile.user is not None)
        self.assertEqual(profile.picture, 'profile_pictures/picture_P.jpg')

    def test_profile_update(self):
        """
        Tests profile update
        """
        user = UserF.create()
        profile = userProfileFactory.create(user=user)
        profile_picture = {
            'picture': 'profile_pictures/picture_P.jpg',
        }
        profile.__dict__.update(profile_picture)
        profile.first_name = 'j'
        profile.last_name = 'jj'
        profile.save()

        user.email = 't@t.com'
        user.save()

        self.assertIsNotNone(profile.picture)
        self.assertIsNotNone(profile.first_name)
        self.assertIsNotNone(profile.last_name)
        self.assertIsNotNone(user.email)

    def test_profile_delete(self):
        """
        Tests profile delete
        """
        user = UserF.create()
        profile = userProfileFactory.create(user=user)
        profile.delete()

        self.assertTrue(profile.pk is None)

    def test_post(self):
        # Log in the test user
        self.client.login(username='testuser', password='testpassword')

        device = TOTPDevice(
            user=self.test_user,
            name='device_name'
        )
        device.save()

        url = reverse('profile', kwargs={'slug': 'testuser'})

        # Send a POST request to the view
        response = self.client.post(url)

        # Assert that the response status code is 302 (Redirect)
        self.assertEqual(response.status_code, 302)

        # Assert that the response redirects to correct path
        self.assertEqual(response.url, '/profile/testuser/')

    def test_post_with_data(self):
        """
        Test update profile from the form page
        """
        user = get_user_model().objects.create(
            is_staff=False,
            is_active=True,
            is_superuser=False,
            username='test',
            email='test@test.com',
        )
        title = userTitleFactory.create(
            id=1,
            name = 'test',
        )
        role = userRoleTypeFactory.create(
            id=1,
            name = 'test',
        )
        device = TOTPDevice(
            user=self.test_user,
            name='device_name'
        )
        device.save()
        # user.first_name = 'Fan'
        # user.last_name = 'Fan'
        # user.email = user.email
        # user.save()
        UserProfile.objects.create(
            user=user,
            title_id=title,
            user_role_type_id=role
        )
        resp = self.client.login(username='testuser', password='testpassword')
        self.assertTrue(resp)

        post_dict = {
            'first-name': 'Fan',
            'last-name': 'Fan',
            'email': user.email,
            'organization': 'Kartoza',
            'profile_picture': '/profile/pic/path',
            'title': '1',
            'role': '1'
        }

        response = self.client.post(
            '/profile/{}/'.format(self.test_user.username), post_dict
        )
        self.assertEqual(response.status_code, 302)
        updated_user = get_user_model().objects.get(id=user.id)
        self.assertEqual(updated_user.first_name, '')
        self.assertIsNotNone(updated_user.user_profile.picture)
        self.assertEqual(user.user_profile.title_id.name, title.name)
        self.assertEqual(user.user_profile.user_role_type_id.name, role.name)

    def test_404(self):
        """
        Test 404 mismatch user
        """
        user = get_user_model().objects.create(
            is_staff=False,
            is_active=True,
            is_superuser=False,
            username='test',
            email='test@test.com',
        )
        device = TOTPDevice(
            user=self.test_user,
            name='device_name'
        )
        device.save()

        resp = self.client.login(username='testuser', password='testpassword')
        self.assertTrue(resp)

        response = self.client.post(
            '/profile/{}/'.format(user.username)
        )
        # if mismatch user
        self.assertEqual(response.status_code, 404)

    def test_context_data(self):
        device = TOTPDevice(
            user=self.test_user,
            name='device_name'
        )
        device.save()
        resp = self.client.login(username='testuser', password='testpassword')
        self.assertTrue(resp)
        response = self.client.get(
            '/profile/{}/'.format(self.test_user.username),
        )
        self.assertEqual(response.status_code, 200)
        context = response.context

        self.assertIn('titles', context)
        self.assertIn('roles', context)
        self.assertIn('object', context)
