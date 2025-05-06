from django import forms
from .models import User, Category, BoardGame, GameCopy, Collection
from django.core.exceptions import ValidationError


class ProfileEditForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["given_name", "family_name", "email", "profile_picture"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            if field != "profile_picture":
                self.fields[field].widget.attrs.update({"class": "form-control"})
            else:
                self.fields[field].widget.attrs.update({"class": "form-control-file"})
                self.fields["profile_picture"].help_text = (
                    "Upload a JPG, PNG, or GIF image (Max 2MB)."
                )

    def clean_profile_picture(
        self,
    ):  # Overriding Djangos default to get our specific message out (only works for the image size msg not type)
        picture = self.cleaned_data.get("profile_picture")

        if picture:
            max_file_size = (
                2 * 1024 * 1024
            )  # 2MB Image size gap, we can shrink if too large
            if picture.size > max_file_size:
                raise ValidationError(
                    "The file you uploaded is too large. Maximum size allowed is 2MB."
                )

        return picture


class BoardGameForm(forms.ModelForm):
    num_copies = forms.IntegerField(
        min_value=1,
        initial=1,
        label="Number of Copies",
        help_text="How many physical copies of this game to add to the library",
    )

    categories = forms.ModelMultipleChoiceField(
        queryset=Category.objects.all(),
        widget=forms.SelectMultiple(attrs={"class": "form-select"}),
    )

    default_pickup_location = forms.ChoiceField(
        choices=GameCopy.PICKUP_LOCATION_CHOICES,
        initial="shannon",
        label="Pickup Location",
        help_text="Default location where this game can be picked up",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    class Meta:
        model = BoardGame
        fields = [
            "title",
            "description",
            "image",
            "min_players",
            "max_players",
            "categories",
            "playing_time",
            "complexity",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "complexity": forms.NumberInput(attrs={"min": 1, "max": 5}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance and self.instance.pk:
            self.fields["num_copies"].initial = self.instance.copies.count()

            # If there are existing copies, set the default pickup location based on the most common one
            if self.instance.copies.exists():
                locations = self.instance.copies.values_list(
                    "pickup_location", flat=True
                )
                location_counts = {}
                for loc in locations:
                    location_counts[loc] = location_counts.get(loc, 0) + 1
                if location_counts:
                    most_common_location = max(
                        location_counts.items(), key=lambda x: x[1]
                    )[0]
                    self.fields["default_pickup_location"].initial = (
                        most_common_location
                    )

    def save(self, commit=True):
        print(f"[INFO] User submitted form with data {self.cleaned_data}")

        # 1) Save the BoardGame itself
        board_game = super().save(commit=False)
        board_game.save()

        # 2) Grab the user’s chosen location
        default_location = self.cleaned_data.get("default_pickup_location", "shannon")

        if commit:
            self.instance.copies.update(pickup_location=default_location)

            # 3b) Then handle creating any *new* copies if num_copies increased
            num_copies = self.cleaned_data.get("num_copies", 1)
            self.save_m2m()
            current_copies = self.instance.copies.count()
            copies_to_create = max(0, num_copies - current_copies)

            for _ in range(copies_to_create):
                GameCopy.objects.create(
                    game=board_game,
                    condition="good",  # Default condition
                    pickup_location=default_location,
                )

        return board_game


class CollectionForm(forms.ModelForm):
    class Meta:
        model = Collection
        fields = ["title", "description", "visibility", "authorized_users"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "authorized_users": forms.SelectMultiple(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        # `user` is passed-through from the view
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        # patrons never need to see the authorised-users widget
        self.fields["authorized_users"].required = False

        # patron? ⇒ hide the “private” option
        if user and (user.is_patron() and not user.is_librarian()):
            self.fields["visibility"].choices = [
                choice
                for choice in self.fields["visibility"].choices
                if choice[0] != "private"
            ]
