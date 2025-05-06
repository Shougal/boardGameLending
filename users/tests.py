from django.test import TestCase, Client
from django.contrib.auth.models import Group
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError
from datetime import timedelta
from .models import User, Category, BoardGame, GameCopy, GameLoan, Review, Collection
from django.urls import reverse


class UserModelTests(TestCase):
    def setUp(self):
        # Create required groups
        self.patron_group = Group.objects.create(name="Patron")
        self.librarian_group = Group.objects.create(name="Librarian")

        # Create test users
        self.regular_user = User.objects.create_user(
            email="testuser@example.com", password="testpass"
        )
        self.staff_user = User.objects.create_user(
            email="staffuser@example.com", password="testpass", is_staff=True
        )
        self.admin_user = User.objects.create_superuser(
            email="adminuser@example.com", password="testpass"
        )

    def test_user_creation(self):
        user = User.objects.get(email="testuser@example.com")
        self.assertEqual(user.email, "testuser@example.com")

    def test_user_is_active(self):
        user = User.objects.get(email="testuser@example.com")
        self.assertTrue(user.is_active)

    def test_user_full_name(self):
        user = User.objects.get(email="testuser@example.com")
        # Test with empty name fields
        self.assertEqual(user.get_full_name(), user.email)

        # Test with populated name fields
        user.given_name = "Test"
        user.family_name = "User"
        self.assertEqual(user.get_full_name(), "Test User")

    def test_user_short_name(self):
        user = User.objects.get(email="testuser@example.com")
        self.assertEqual(user.get_short_name(), "testuser")

        user.given_name = "Test"
        self.assertEqual(user.get_short_name(), "Test")

    def test_user_groups(self):
        # Regular user should be in Patron group
        self.assertTrue(self.regular_user.is_patron())
        self.assertFalse(self.regular_user.is_librarian())
        self.assertFalse(self.regular_user.is_admin())

        # Add staff to librarian group
        self.staff_user.groups.add(self.librarian_group)
        self.assertTrue(self.staff_user.is_librarian())

        # Admin should be admin
        self.assertTrue(self.admin_user.is_admin())


class CategoryModelTests(TestCase):
    def setUp(self):
        self.category, _ = Category.objects.get_or_create(
            name="Strategy",
        )

    def test_category_creation(self):
        self.assertEqual(self.category.name, "Strategy")

    def test_category_string_representation(self):
        self.assertEqual(str(self.category), "Strategy")


class BoardGameModelTests(TestCase):
    def setUp(self):
        self.category1, _ = Category.objects.get_or_create(name="Strategy")
        self.category2, _ = Category.objects.get_or_create(name="Family")

        self.game = BoardGame.objects.create(
            title="Catan",
            description="A popular resource management game",
            min_players=3,
            max_players=4,
            playing_time=60,
            complexity=2,
        )
        self.game.categories.add(self.category1, self.category2)

        # Create a copy of the game
        self.game_copy = GameCopy.objects.create(game=self.game, condition="excellent")

    def test_boardgame_creation(self):
        self.assertEqual(self.game.title, "Catan")
        self.assertEqual(self.game.min_players, 3)
        self.assertEqual(self.game.max_players, 4)

    def test_boardgame_categories(self):
        self.assertEqual(self.game.categories.count(), 2)
        self.assertIn(self.category1, self.game.categories.all())
        self.assertIn(self.category2, self.game.categories.all())

    def test_boardgame_string_representation(self):
        self.assertEqual(str(self.game), "Catan")

    def test_available_copies_count(self):
        self.assertEqual(self.game.available_copies_count(), 1)

        # Mark the copy as unavailable
        self.game_copy.is_available = False
        self.game_copy.save()
        self.assertEqual(self.game.available_copies_count(), 0)

    def test_is_available_property(self):
        self.assertTrue(self.game.is_available)

        # Mark the copy as unavailable
        self.game_copy.is_available = False
        self.game_copy.save()
        self.assertFalse(self.game.is_available)

    def test_average_rating_property(self):
        # With no reviews
        self.assertIsNone(self.game.average_rating)

        # Create a user and add reviews
        user = User.objects.create_user(
            email="test@example.com", password="password123"
        )
        Review.objects.create(user=user, game=self.game, rating=4)
        self.assertEqual(self.game.average_rating, 4.0)

        # Add another review
        user2 = User.objects.create_user(
            email="test2@example.com", password="password123"
        )
        Review.objects.create(user=user2, game=self.game, rating=5)
        self.assertEqual(self.game.average_rating, 4.5)


class GameCopyModelTests(TestCase):
    def setUp(self):
        self.game = BoardGame.objects.create(
            title="Chess", min_players=2, max_players=2
        )
        self.copy = GameCopy.objects.create(
            game=self.game, condition="good", notes="Missing one pawn"
        )

    def test_gamecopy_creation(self):
        self.assertEqual(self.copy.game, self.game)
        self.assertEqual(self.copy.condition, "good")
        self.assertEqual(self.copy.notes, "Missing one pawn")
        self.assertTrue(self.copy.is_available)

    def test_gamecopy_string_representation(self):
        self.assertEqual(str(self.copy), f"Chess (#{self.copy.pk})")

    def test_update_availability(self):
        user = User.objects.create_user(
            email="borrower@example.com", password="testpass"
        )

        # Create a loan
        loan = GameLoan.objects.create(
            user=user, game_copy=self.copy, due_date=timezone.now() + timedelta(days=14)
        )

        # Copy should be marked as unavailable
        self.copy.refresh_from_db()
        self.assertFalse(self.copy.is_available)

        # Return the game
        loan.mark_as_returned()

        # Copy should be available again
        self.copy.refresh_from_db()
        self.assertTrue(self.copy.is_available)


class GameLoanModelTests(TestCase):
    def setUp(self):
        # Create groups
        Group.objects.create(name="Patron")

        # Create user, game, and copy
        self.user = User.objects.create_user(
            email="borrower@example.com", password="testpass"
        )
        self.game = BoardGame.objects.create(
            title="Monopoly", min_players=2, max_players=8
        )
        self.copy = GameCopy.objects.create(game=self.game, condition="good")

        # Create a loan
        self.loan = GameLoan.objects.create(
            user=self.user,
            game_copy=self.copy,
            due_date=timezone.now() + timedelta(days=14),
        )

    def test_gameloan_creation(self):
        self.assertEqual(self.loan.user, self.user)
        self.assertEqual(self.loan.game_copy, self.copy)
        self.assertEqual(self.loan.status, "borrowed")
        self.assertFalse(self.loan.returned)

    def test_gameloan_string_representation(self):
        self.assertEqual(str(self.loan), f"Monopoly - {self.user.get_full_name()}")

    def test_loan_affects_copy_availability(self):
        self.copy.refresh_from_db()
        self.assertFalse(self.copy.is_available)

    def test_mark_as_returned(self):
        self.loan.mark_as_returned(condition="excellent")

        # Check loan status
        self.assertTrue(self.loan.returned)
        self.assertIsNotNone(self.loan.returned_on)
        self.assertEqual(self.loan.status, "returned")

        # Check copy availability and condition
        self.copy.refresh_from_db()
        self.assertTrue(self.copy.is_available)
        self.assertEqual(self.copy.condition, "excellent")

    def test_is_overdue_property(self):
        # Not overdue initially
        self.assertFalse(self.loan.is_overdue)

        # Set due date in the past
        self.loan.due_date = timezone.now() - timedelta(days=1)
        self.loan.save()

        self.assertTrue(self.loan.is_overdue)
        self.assertEqual(self.loan.status, "overdue")


class ReviewModelTests(TestCase):
    def setUp(self):
        # Create groups
        Group.objects.create(name="Patron")

        # Create user and game
        self.user = User.objects.create_user(
            email="reviewer@example.com", password="testpass"
        )
        self.game = BoardGame.objects.create(title="Risk", min_players=2, max_players=6)

        # Create a review
        self.review = Review.objects.create(
            user=self.user,
            game=self.game,
            rating=4,
            title="Great game",
            comment="Lots of fun but takes a long time to play",
        )

    def test_review_creation(self):
        self.assertEqual(self.review.user, self.user)
        self.assertEqual(self.review.game, self.game)
        self.assertEqual(self.review.rating, 4)
        self.assertEqual(self.review.title, "Great game")

    def test_review_string_representation(self):
        self.assertEqual(str(self.review), f"Risk - 4★ by {self.user.get_full_name()}")

    def test_unique_constraint(self):
        # Try to create another review for the same user and game
        with self.assertRaises(IntegrityError):
            Review.objects.create(user=self.user, game=self.game, rating=5)

    def test_rating_validation(self):
        # Test invalid ratings
        with self.assertRaises(ValidationError):
            invalid_review = Review(
                user=self.user, game=self.game, rating=6  # Invalid rating > 5
            )
            invalid_review.full_clean()


class CollectionModelTests(TestCase):
    def setUp(self):
        # Create required groups
        self.patron_group = Group.objects.create(name="Patron")
        self.librarian_group = Group.objects.create(name="Librarian")

        # Create test users
        self.patron = User.objects.create_user(
            email="patron@example.com", password="testpass"
        )

        self.librarian = User.objects.create_user(
            email="librarian@example.com", password="testpass", is_staff=True
        )
        self.librarian.groups.add(self.librarian_group)

        self.admin = User.objects.create_superuser(
            email="admin@example.com", password="testpass"
        )

        self.other_user = User.objects.create_user(
            email="other@example.com", password="testpass"
        )

        # Create games
        self.game1 = BoardGame.objects.create(
            title="Ticket to Ride", min_players=2, max_players=5
        )

        self.game2 = BoardGame.objects.create(
            title="Pandemic", min_players=2, max_players=4
        )

        # Create collections
        self.public_collection = Collection.objects.create(
            title="Family Games",
            description="Games for family game night",
            creator=self.patron,
            visibility="public",
        )

        self.private_collection = Collection.objects.create(
            title="Strategy Favorites",
            description="My favorite strategy games",
            creator=self.librarian,
            visibility="private",
        )

    def test_collection_creation(self):
        self.assertEqual(self.public_collection.title, "Family Games")
        self.assertEqual(self.public_collection.visibility, "public")
        self.assertEqual(self.private_collection.title, "Strategy Favorites")
        self.assertEqual(self.private_collection.visibility, "private")

    def test_collection_string_representation(self):
        self.assertEqual(str(self.public_collection), "Family Games")
        self.assertEqual(str(self.private_collection), "Strategy Favorites")

    def test_collection_games_relationship(self):
        # Add games to collections
        self.public_collection.games.add(self.game1)
        self.private_collection.games.add(self.game2)

        # Check relationships
        self.assertEqual(self.public_collection.games.count(), 1)
        self.assertEqual(self.private_collection.games.count(), 1)
        self.assertIn(self.game1, self.public_collection.games.all())
        self.assertIn(self.game2, self.private_collection.games.all())

    def test_patron_collection_visibility_enforcement(self):
        # Patrons can only create public collections
        private_patron_collection = Collection.objects.create(
            title="Attempt Private Collection",
            creator=self.patron,
            visibility="private",
        )

        # The save method should enforce public visibility
        self.assertEqual(private_patron_collection.visibility, "public")

    def test_is_private_property(self):
        self.assertFalse(self.public_collection.is_private)
        self.assertTrue(self.private_collection.is_private)

    def test_can_user_access(self):
        # Public collections should be accessible to all
        self.assertTrue(self.public_collection.can_user_access(self.patron))
        self.assertTrue(self.public_collection.can_user_access(self.librarian))
        self.assertTrue(self.public_collection.can_user_access(self.admin))
        self.assertTrue(self.public_collection.can_user_access(self.other_user))

        # Private collections accessible only to creator, librarians, and authorized users
        self.assertFalse(self.private_collection.can_user_access(self.patron))
        self.assertTrue(
            self.private_collection.can_user_access(self.librarian)
        )  # Creator
        self.assertFalse(self.private_collection.can_user_access(self.admin))  # Admin
        self.assertFalse(self.private_collection.can_user_access(self.other_user))

        # Add authorized user
        self.private_collection.authorized_users.add(self.other_user)
        self.assertTrue(self.private_collection.can_user_access(self.other_user))

    def test_can_add_game(self):
        # Create a new game not in any collection
        new_game = BoardGame.objects.create(
            title="Carcassonne", min_players=2, max_players=5
        )

        # Should be able to add to either public or private collection
        self.assertTrue(self.public_collection.can_add_game(new_game))
        self.assertTrue(self.private_collection.can_add_game(new_game))

        # Add to private collection
        self.private_collection.games.add(new_game)

        # Now should not be able to add to public collection
        self.assertFalse(self.public_collection.can_add_game(new_game))

        # Create another new game
        another_game = BoardGame.objects.create(
            title="Azul", min_players=2, max_players=4
        )

        # Add to public collection
        self.public_collection.games.add(another_game)

        # Should not be able to add to private collection
        self.assertFalse(self.private_collection.can_add_game(another_game))

    def test_collection_absolute_url(self):
        url = self.public_collection.get_absolute_url()
        self.assertEqual(url, f"/collections/{self.public_collection.pk}/")


class AuthorizationViewTests(TestCase):
    def setUp(self):
        self.client = Client()

        # Create and assign groups
        self.patron_group = Group.objects.create(name="Patron")

        # Create two users
        self.user1 = User.objects.create_user(
            email="user1@example.com", password="testpass"
        )
        self.user2 = User.objects.create_user(
            email="user2@example.com", password="testpass"
        )

    def test_redirect_if_not_logged_in(self):
        url = reverse("profile", kwargs={"pk": self.user1.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_user_cannot_access_another_users_profile(self):
        self.client.login(email="user1@example.com", password="testpass")
        url = reverse("profile", kwargs={"pk": self.user2.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)
