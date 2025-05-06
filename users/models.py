from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
    Group,
)
from django.db import models
from django.urls import reverse
from django.templatetags.static import static
from django.utils import timezone
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from datetime import timedelta


class UserManager(BaseUserManager):
    """Custom user manager for the User model with email as the unique identifier."""

    def _create_user(self, email, password, is_staff, is_superuser, **extra_fields):
        """Create and save a user with the given email and password."""
        if not email:
            raise ValueError("Users must have an email address")

        email = self.normalize_email(email)
        user = self.model(
            email=email, is_staff=is_staff, is_superuser=is_superuser, **extra_fields
        )

        user.set_password(password)
        user.save(using=self._db)

        if not is_superuser and not is_staff:
            patron_group, _ = Group.objects.get_or_create(name="Patron")
            user.groups.add(patron_group)

        return user

    def create_user(self, email, password=None, **extra_fields):
        """Create and save a regular user with the given email and password."""
        extra_fields.setdefault("is_staff", False)  # note this is a refactor change
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        """Create and save a superuser with the given email and password."""
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self._create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """Custom user model that uses email instead of username for authentication."""

    email = models.EmailField(max_length=256, unique=True)
    given_name = models.CharField(max_length=254, blank=True)
    family_name = models.CharField(max_length=254, blank=True)
    is_staff = models.BooleanField(
        default=False,
        help_text="Designates whether this user can access the admin site.",
    )
    is_superuser = models.BooleanField(
        default=False,
        help_text="Designates that this user has all permissions without explicitly assigning them.",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Designates whether this user should be treated as active.",
    )
    last_login = models.DateTimeField(null=True, blank=True)
    date_joined = models.DateTimeField(auto_now_add=True)
    profile_picture = models.ImageField(
        upload_to="profile_pictures/", blank=True, null=True
    )

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        ordering = ["email"]

    def __str__(self):
        return self.email

    def get_username(self):
        """Return the email as username for this user."""
        return self.email

    def is_librarian(self):
        """Check if user belongs to the Librarian group."""
        return self.groups.filter(name="Librarian").exists()

    def is_patron(self):
        """Check if user is a patron (not librarian or admin)."""
        return self.groups.filter(name="Patron").exists()

    def is_admin(self):
        """Check if user is an admin."""
        return self.is_superuser

    def get_absolute_url(self):
        """Return the URL to access a particular user."""
        return reverse("profile", kwargs={"pk": self.pk})

    def get_profile_picture_url(self):
        """Return the URL of the user's profile picture or a default image."""
        if self.profile_picture and hasattr(self.profile_picture, "url"):
            return self.profile_picture.url
        return static("images/default-avatar.jpg")

    def get_full_name(self):
        """Return the user's full name."""
        full_name = f"{self.given_name} {self.family_name}".strip()
        return full_name if full_name else self.email

    def get_short_name(self):
        """Return the user's given name or first part of email."""
        return self.given_name if self.given_name else self.email.split("@")[0]


class Category(models.Model):
    """Model representing a board game category/genre."""

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name = "Category"
        verbose_name_plural = "Categories"
        ordering = ["name"]

    def __str__(self):
        return self.name


class BoardGame(models.Model):
    """Model representing a board game."""

    title = models.CharField(max_length=255, db_index=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="board_games/", blank=True, null=True)
    categories = models.ManyToManyField(Category, related_name="games", blank=True)
    min_players = models.PositiveSmallIntegerField(default=1)
    max_players = models.PositiveSmallIntegerField(default=4)
    playing_time = models.PositiveIntegerField(
        help_text="Average playing time in minutes",
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(10000)],
    )
    complexity = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Game complexity from 1 (simple) to 5 (complex)",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Board Game"
        verbose_name_plural = "Board Games"
        ordering = ["title"]
        indexes = [models.Index(fields=["title"])]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("boardgame-detail", kwargs={"pk": self.pk})

    def get_image_url(self):
        """Return the URL of the game's image or a default image."""
        if self.image and hasattr(self.image, "url"):
            return self.image.url
        return static("images/default-game.png")

    def available_copies_count(self):
        """Return the number of available copies of this game."""
        return self.copies.filter(is_available=True).count()

    def can_add_to_collection(self, collection):
        """Check if this game can be added to the given collection."""
        # If the collection is public, the game can be added if it's not in a private collection
        if collection.visibility == "public":
            return not self.collections.filter(visibility="private").exists()

        # If the collection is private, the game can only be added if it's not in any collection
        if collection.visibility == "private":
            return not self.collections.exists()

        return False

    @property
    def is_available(self):
        """Check if at least one copy of the game is available for borrowing."""
        return self.available_copies_count() > 0

    @property
    def average_rating(self):
        """Calculate the average rating for this board game."""
        ratings = self.reviews.values_list("rating", flat=True)
        return round(sum(ratings) / len(ratings), 1) if ratings else None


class GameCopy(models.Model):
    """Model representing a physical copy of a board game."""

    CONDITION_CHOICES = [
        ("new", "New"),
        ("excellent", "Excellent"),
        ("good", "Good"),
        ("fair", "Fair"),
        ("poor", "Poor"),
        ("damaged", "Damaged"),
    ]

    PICKUP_LOCATION_CHOICES = [
        ("shannon", "Shannon Library"),
        ("clark", "Clark Library"),
        ("clemons", "Clemons Library"),
    ]

    game = models.ForeignKey(BoardGame, on_delete=models.CASCADE, related_name="copies")
    acquisition_date = models.DateField(
        default=timezone.now,
        help_text="Date when this copy was added to the collection",
    )
    condition = models.CharField(
        max_length=20, choices=CONDITION_CHOICES, default="good"
    )
    pickup_location = models.CharField(
        max_length=20,
        choices=PICKUP_LOCATION_CHOICES,
        default="shannon",
        help_text="Location where this game copy can be picked up",
    )
    notes = models.TextField(blank=True)
    is_available = models.BooleanField(
        default=True, help_text="Whether this copy is available for borrowing"
    )

    class Meta:
        verbose_name = "Game Copy"
        verbose_name_plural = "Game Copies"
        ordering = ["game__title", "pk"]

    def __str__(self):
        return f"{self.game.title} (#{self.pk})"

    def update_availability(self):
        """Update availability status based on active loans."""
        active_loan_exists = self.loans.filter(returned=False).exists()
        if self.is_available == active_loan_exists:
            self.is_available = not active_loan_exists
            self.save(update_fields=["is_available"])


class GameLoan(models.Model):
    """Model representing a loan of a board game copy to a user."""

    STATUS_CHOICES = [
        ("borrowed", "Borrowed"),
        ("returned", "Returned"),
        ("overdue", "Overdue"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="borrowed_games",
    )
    game_copy = models.ForeignKey(
        GameCopy, on_delete=models.CASCADE, related_name="loans", default=None
    )
    borrowed_on = models.DateTimeField(default=timezone.now)
    due_date = models.DateTimeField()
    returned = models.BooleanField(default=False)
    returned_on = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="borrowed")
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = "Game Loan"
        verbose_name_plural = "Game Loans"
        ordering = ["-borrowed_on"]
        indexes = [
            models.Index(fields=["user", "returned"]),
            models.Index(fields=["due_date"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.game_copy.game.title} - {self.user.get_full_name()}"

    def save(self, *args, **kwargs):
        # Set due date if not set (default to 2 weeks)
        if not self.due_date:
            self.due_date = timezone.now() + timedelta(days=14)

        # Update status based on returned flag and due date
        if self.returned:
            self.status = "returned"
            # Set returned_on date if not already set
            if not self.returned_on:
                self.returned_on = timezone.now()
        elif self.due_date < timezone.now():
            self.status = "overdue"
        else:
            self.status = "borrowed"

        # Save the loan
        super().save(*args, **kwargs)

        # Update game copy availability
        self.game_copy.update_availability()

    @property
    def is_overdue(self):
        """Check if this loan is overdue."""
        return not self.returned and self.due_date < timezone.now()

    def mark_as_returned(self, condition=None):
        """Mark this loan as returned and optionally update game condition."""
        self.returned = True
        self.returned_on = timezone.now()
        self.status = "returned"

        # Update condition if provided
        if condition and condition in dict(self.game_copy.CONDITION_CHOICES):
            self.game_copy.condition = condition
            self.game_copy.save(update_fields=["condition"])

        self.save()


class Review(models.Model):
    """Model representing a user review of a board game."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews"
    )
    game = models.ForeignKey(
        BoardGame, on_delete=models.CASCADE, related_name="reviews"
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Rating from 1 to 5 stars",
    )
    title = models.CharField(max_length=100, blank=True)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Review"
        verbose_name_plural = "Reviews"
        ordering = ["-created_at"]
        # Ensure a user can only review a game once
        unique_together = [["user", "game"]]

    def __str__(self):
        return f"{self.game.title} - {self.rating}★ by {self.user.get_full_name()}"


class Collection(models.Model):
    """Model representing a collection of board games."""

    VISIBILITY_CHOICES = [
        ("public", "Public"),
        ("private", "Private"),
    ]

    title = models.CharField(max_length=255, db_index=True)
    description = models.TextField(blank=True)
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="created_collections",
    )
    games = models.ManyToManyField(BoardGame, related_name="collections", blank=True)
    visibility = models.CharField(
        max_length=10, choices=VISIBILITY_CHOICES, default="public"
    )
    authorized_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="accessible_collections",
        blank=True,
        help_text="Users who can view this private collection",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Collection"
        verbose_name_plural = "Collections"
        ordering = ["title"]
        indexes = [models.Index(fields=["title"])]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("collection_detail", kwargs={"pk": self.pk})

    def save(self, *args, **kwargs):
        # Enforce that patron collections are always public
        if self.creator.is_patron() and not self.creator.is_librarian():
            self.visibility = "public"
        super().save(*args, **kwargs)

    @property
    def is_private(self):
        """Check if collection is private."""
        return self.visibility == "private"

    def can_user_access(self, user):
        """Determine if a user can access this collection."""
        # Public collections are accessible to all
        if self.visibility == "public":
            return True

        # Private collections are accessible to:
        # 1. The creator
        # 2. Librarians
        # 3. Authorized users
        if user.is_authenticated:
            if user == self.creator or user.is_librarian():
                return True
            return self.authorized_users.filter(pk=user.pk).exists()

        return False

    def can_add_game(self, game):
        """Check if a game can be added to this collection based on rules."""
        # If this is a public collection, the game can be added if it's not in a private collection
        if self.visibility == "public":
            return not game.collections.filter(visibility="private").exists()

        # If this is a private collection, the game can only be added if it's not in any collection
        if self.visibility == "private":
            return not game.collections.exists()

        return False


class BorrowRequest(models.Model):
    REQUEST_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("denied", "Denied"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="borrow_requests",
    )
    game = models.ForeignKey(
        BoardGame, on_delete=models.CASCADE, related_name="borrow_requests"
    )
    status = models.CharField(
        max_length=20, choices=REQUEST_STATUS_CHOICES, default="pending"
    )
    requested_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"BorrowRequest({self.user}, {self.game}, {self.status})"


class CollectionAccessRequest(models.Model):
    REQUEST_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("denied", "Denied"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="collection_requests",
    )
    collection = models.ForeignKey(
        Collection, on_delete=models.CASCADE, related_name="access_requests"
    )
    status = models.CharField(
        max_length=20, choices=REQUEST_STATUS_CHOICES, default="pending"
    )
    requested_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"CollectionAccessRequest({self.user}, {self.collection}, {self.status})"
