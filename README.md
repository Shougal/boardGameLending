### Sources
Note that we used the starter code from [here](https://github.com/heroku/python-getting-started.git)

## Database Models Documentation

### Overview
This section describes the database schema for the board game library management system. The system consists of models for users, board games, categories, physical copies, loans, and reviews.

### Auth/User Models

#### UserManager
Custom user manager that enables email-based authentication instead of username.
- Provides methods for creating regular users and superusers
- Automatically assigns new users to the "Patron" group

#### User
Custom user model that uses email as the primary identifier instead of username.
- **Fields**: email, given_name, family_name, is_staff, is_superuser, is_active, profile_picture
- **Methods**:
    - `is_librarian()`: Checks if user belongs to Librarian group
    - `is_patron()`: Checks if user belongs to Patron group
    - `is_admin()`: Checks if user is a superuser
    - `get_profile_picture_url()`: Returns URL to profile picture or default image
    - `get_full_name()`: Returns user's full name or email if name not provided
    - `get_short_name()`: Returns given name or first part of email

### Board Game Models

#### Category
Represents a board game category or genre.
- **Fields**: name, description
- Used for categorizing and filtering board games

#### BoardGame
Represents a board game in the library collection.
- **Fields**: title, description, image, categories (M2M), min_players, max_players, playing_time, complexity
- **Methods**:
    - `get_image_url()`: Returns URL to game image or default
    - `available_copies_count()`: Returns number of available copies
    - `is_available`: Property that checks if at least one copy is available
    - `average_rating`: Property that calculates average rating from reviews

#### GameCopy
Represents a physical copy of a board game that can be borrowed.
- **Fields**: game (FK), acquisition_date, condition, notes, is_available
- **Condition options**: new, excellent, good, fair, poor, damaged
- **Methods**:
    - `update_availability()`: Updates availability based on active loans


#### Collection
Model representing a collection of board games.
- **Fields**: creator (FK), games (M2M), authorized_users (M2M), title, description, visibility, created_at, updated_at
- **Methods**:
    - `__str__()`: Returns the title of the collection
    - `get_absolute_url()`: Returns URL to access the collection detail view
    - `save()`: Ensures patron collections are always set to public visibility
    - `is_private` (property): Checks if collection has private visibility setting
    - `can_user_access(user)`: Determines if a user can access this collection based on visibility and permissions
    - `can_add_game(game)`: Checks if a game can be added to this collection based on visibility rules


### Lending System Models

#### GameLoan
Tracks the borrowing of game copies by users.
- **Fields**: user (FK), game_copy (FK), borrowed_on, due_date, returned, returned_on, status, notes
- **Status options**: borrowed, returned, overdue
- **Methods**:
    - `is_overdue`: Property that checks if loan is past due date
    - `mark_as_returned()`: Marks the loan as returned and updates game copy availability

#### Review
Stores user reviews and ratings for board games.
- **Fields**: user (FK), game (FK), rating (1-5), title, comment
- Enforces one review per user per game
- Contributes to the board game's average rating

### Relationships
- Users can borrow multiple games (one-to-many: User → GameLoan)
- Users can review multiple games (one-to-many: User → Review)
- Board games can have multiple categories (many-to-many: BoardGame ↔ Category)
- Board games can have multiple physical copies (one-to-many: BoardGame → GameCopy)
- Game copies can have multiple loan records over time (one-to-many: GameCopy → GameLoan)
- Board games can have multiple reviews (one-to-many: BoardGame → Review)

## Random Notes

#### Notes on Adding New Views
Right now the way the base template works is we are required to pass a context object harvested from the `request.user` dictionary. An example from `users/views.py` is given below.

```python
def index(request):
    context = dict()
    user = request.user
    if user.is_authenticated:
        context["is_authenticated"] = True
        context["is_librarian"] = user.is_librarian()
        context["is_patron"] = user.is_patron()
        context["given_name"] = user.given_name
        context["email"] = user.email
    else:
        context["is_authenticated"] = False
    return render(request, "index.html", context)
```
This will need to be done for any page that doesn't use the header. I've turned it into a helper function called `create_context` in the `views.py`. If you have an existing context you can combine the "auth_context" created in the above function like the below.

```python
render(request, "users/profile.html", {
    "user": request.user,
    "borrowed_games": borrowed_games,
    "active_borrows": active_borrows,
    "games_lent_out": games_lent_out,
    "today": now().date(),
} | auth_context)
```

### Deploy on Heroku [Cedar](https://devcenter.heroku.com/articles/generations#cedar)
Our app is set to deploy by default on `main`. You cannot directly commit to main, if you would like to make changes open a PR and once the PR is merged your code will automatically deploy.

### Notes on Code Style
Black is probably the best industry-standard Python code formatter, so I've bundled it with the dependencies for the project. If someone can figure out a way to auto-style on commit that would be best (i.e. with GitHub pre-commit hooks), but for now run `black .` in the root folder of the repository to format the entire project at once before you commit.

### Notes on the Database
`is_staff` is not related to librarians but is instead a field representing users who have access to the admin page. Instead the `is_librarian` field is used to denote librarians. Patrons are users for whom both `is_staff` and `is_librarian` are false.

If you're running a fresh copy of the project (i.e. deleted the database) make sure you run `python manage.py creategroups`.

### Notes on Managing `static` files
Not sure if this is an error I created, but static files don't seem to work unless you run `python manage.py collectstatic` locally before running the server. It works in `prod` though.

### Notes on Managing Dependencies
The server uses `requirements.txt`, but I provide instructions for using `conda` to manage Python dependencies as well if you haven't already. I use this for local development, it makes managing Python dependencies much easier, see instructions for installation [here](https://kirenz.github.io/codelabs/codelabs/miniforge-setup/#2).

### Notes on AWS S3 Remote Storage 
Our chosen tool for image storage is AWS S3. Anytime an image is uploaded ensure the size of the image < 2 MB. We shouldn't have any issues with LFI so don't worry about sanitizing image data. It might be worth checking that the image they uploaded is a valid image (i.e. if its a PNG we can verify the CRCs of the PNG, the magic bytes, and the IEND). Same with JPGs and other things. We can limit it to PNGs and JPGs for ease of use. The base URL for the bucket is `https://cs-3240-board-game-bucket.s3.us-east-1.amazonaws.com`. The bucket contains the folders "board-games" and "profiles". "board-games" is where we'll upload all our board game images and profiles is where profile pictures go. The AWS credentials are in the `.env` file, if you have any issues send a DM in Discord.

To create the environment in `conda`:
```bash
conda env create -f environment.yml
```

To update the environment file locally after using `pip install` or `conda install`:
```bash
conda env export > environment.yml
```

To update the remote server:
```bash
pip freeze > requirements.txt
```

