from django.shortcuts import redirect, render, get_object_or_404, HttpResponseRedirect
from django.core.exceptions import PermissionDenied
from django.contrib.auth import logout
from django.views.decorators.http import require_POST
from .models import (
    User,
    GameLoan,
    BoardGame,
    Collection,
    Category,
    GameCopy,
    BorrowRequest,
    CollectionAccessRequest,
    Review,
    Group,
)
from django.utils import timezone
from django.db import models
from django.contrib import messages
from .forms import ProfileEditForm, BoardGameForm, CollectionForm
from datetime import timedelta
from django.urls import reverse
from .s3_utils import generate_presigned_url


def is_librarian(user):
    return user.is_authenticated and user.is_librarian()


def create_context(user: dict) -> dict:
    context = dict()
    if user.is_authenticated:
        context["is_authenticated"] = True
        context["is_librarian"] = user.is_librarian()
        context["is_patron"] = user.is_patron()
        context["given_name"] = user.given_name
        context["email"] = user.email
    else:
        context["is_authenticated"] = False
    print(f"[INFO] User Context is {context}")
    return context


def index(request):
    user = request.user
    images = {
        "catan": generate_presigned_url("images/catan.jpg"),
        "ticket_to_ride": generate_presigned_url("images/ticket_to_ride.jpg"),
        "azul": generate_presigned_url("images/azul.jpg"),
        "board_games_on_table": generate_presigned_url(
            "images/board_games_on_table.jpg"
        ),
    }
    context = create_context(user) | images

    # Add welcome message if authenticated
    if user.is_authenticated:
        role = "Librarian" if user.is_librarian() else "Patron"
        welcome_message = f"Welcome, {user.get_short_name()} ({role})!"
        context["welcome_message"] = welcome_message

    print(context)
    return render(request, "index.html", context)


def logout_view(request):
    logout(request)
    return redirect("/")


def user_profile(request, pk):
    user = get_object_or_404(User, pk=pk)
    if request.user != user:
        raise PermissionDenied

    borrowed_games = GameLoan.objects.filter(user=user).order_by("-borrowed_on")
    active_borrows = borrowed_games.filter(returned=False)

    context = {
        "user": user,
        "previous_loans": borrowed_games,
        "active_loans": active_borrows,
        "borrow_requests": request.user.borrow_requests.all().order_by("-requested_at"),
        "collection_requests": request.user.collection_requests.all().order_by(
            "-requested_at"
        ),
    } | create_context(request.user)

    return render(request, "users/profile.html", context)


def edit_profile(request):
    if not request.user.is_authenticated:
        raise PermissionDenied

    if request.method == "POST":
        form = ProfileEditForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            return redirect("profile", pk=request.user.pk)
    else:
        form = ProfileEditForm(instance=request.user)

    context = {"form": form} | create_context(request.user)

    return render(request, "users/edit_profile.html", context)


def manage_board_games(request):
    """View for librarians to manage board games."""
    if not is_librarian(request.user):
        raise PermissionDenied
    board_games = BoardGame.objects.all().order_by("title")

    auth_context = create_context(request.user)
    context = {
        "board_games": board_games,
    } | auth_context

    return render(request, "users/board_game_management.html", context)


def add_board_game(request):
    """View for librarians to add a new board game."""
    if not is_librarian(request.user):
        raise PermissionDenied

    if request.method == "POST":
        form = BoardGameForm(request.POST, request.FILES)
        if form.is_valid():
            board_game = form.save()
            num_copies = form.cleaned_data.get("num_copies", 1)
            messages.success(
                request,
                f"Board game '{board_game.title}' added successfully with {num_copies} copies!",
            )
            return redirect("manage_board_games")
    else:
        form = BoardGameForm()

    auth_context = create_context(request.user)
    context = {
        "form": form,
        "action": "Add",
    } | auth_context

    return render(request, "users/board_game_form.html", context)


def edit_board_game(request, pk):
    """View for librarians to edit an existing board game."""
    if not is_librarian(request.user):
        raise PermissionDenied

    board_game = get_object_or_404(BoardGame, pk=pk)
    initial_copies_count = board_game.copies.count()

    if request.method == "POST":
        form = BoardGameForm(request.POST, request.FILES, instance=board_game)
        if form.is_valid():
            board_game = form.save()

            new_copies_count = form.cleaned_data.get("num_copies", 1)

            if new_copies_count > initial_copies_count:
                copies_added = new_copies_count - initial_copies_count
                messages.success(
                    request,
                    f"Board game '{board_game.title}' updated with {copies_added} new copies added!",
                )
            else:
                messages.success(
                    request, f"Board game '{board_game.title}' updated successfully!"
                )

            return redirect("manage_board_games")
    else:
        form = BoardGameForm(instance=board_game)

    auth_context = create_context(request.user)
    context = {
        "form": form,
        "board_game": board_game,
        "categories": list(board_game.categories.all()),
        "action": "Edit",
    } | auth_context

    return render(request, "users/board_game_form.html", context)


def delete_board_game(request, pk):
    """View for librarians to delete a board game."""
    if not is_librarian(request.user):
        raise PermissionDenied

    board_game = get_object_or_404(BoardGame, pk=pk)

    if request.method == "POST":
        title = board_game.title
        board_game.delete()
        messages.success(request, f"'{title}' has been deleted.")
        return redirect("manage_board_games")

    # If not POST, redirect to management page
    return redirect("manage_board_games")


def board_game_detail(request, pk):
    """View for displaying detailed information about a specific board game."""
    if not request.user.is_authenticated:
        raise PermissionDenied

    game = get_object_or_404(BoardGame, pk=pk)

    # Get available copies with their pickup locations
    available_copies = game.copies.filter(is_available=True)

    # Check if user has borrowed the game:
    has_borrowed = GameLoan.objects.filter(
        user=request.user, game_copy__game=game, returned=True
    ).exists()

    # check if user has previously made a review
    review = Review.objects.filter(user=request.user, game=game).first()

    context = {
        "game": game,
        "categories": list(game.categories.all()),
        "available_copies": available_copies,
        "existing_review": review,
        "has_borrowed": has_borrowed,
    } | create_context(request.user)

    return render(request, "users/board_game_detail.html", context)


def board_game_catalogue(request):
    """View for users to browse and search the board game collection."""
    # Exclude games that are in any private collection
    games = BoardGame.objects.exclude(collections__visibility="private").order_by(
        "title"
    )

    # Search functionality
    search_query = request.GET.get("search", "")
    if search_query:
        games = games.filter(
            models.Q(title__icontains=search_query)
            | models.Q(description__icontains=search_query)
            | models.Q(categories__name__icontains=search_query)
        ).distinct()

    # Filter by complexity
    complexity = request.GET.get("complexity", "")
    if complexity and complexity.isdigit():
        games = games.filter(complexity=int(complexity))

    # Filter by player count
    players = request.GET.get("players", "")
    if players and players.isdigit():
        players_count = int(players)
        games = games.filter(
            min_players__lte=players_count, max_players__gte=players_count
        )

    # Filter by availability
    availability = request.GET.get("availability", "")
    if availability and availability == "available":
        games = games.filter(copies__is_available=True).distinct()

    # Get all categories for filter options
    categories = Category.objects.all().order_by("name")

    # Filter by category
    category = request.GET.get("category", "")
    if category:
        games = games.filter(categories__name=category)

    context = {
        "games": games,
        "categories": categories,
        "search_query": search_query,
        "complexity": complexity,
        "players": players,
        "availability": availability,
        "selected_category": category,
    } | create_context(request.user)

    return render(request, "users/board_game_catalogue.html", context)


def collection_list(request):
    """View for browsing all collections."""
    collections = Collection.objects.all().order_by("title")

    if not request.user.is_authenticated:
        # Anonymous users see only public collections.
        collections = collections.filter(visibility="public")

    # Search functionality
    search_query = request.GET.get("search", "")
    if search_query:
        collections = collections.filter(
            models.Q(title__icontains=search_query)
            | models.Q(description__icontains=search_query)
        ).distinct()

    # Filtering by visiblity (public or private collections)
    visibility_filter = request.GET.get("visibility", "")
    if visibility_filter in ["public", "private"]:
        collections = collections.filter(visibility=visibility_filter)

    # Showing collections created by me (the user)
    creator_filter = request.GET.get("creator", "")
    if creator_filter:
        collections = collections.filter(creator__id=creator_filter)

    # Get all users who created collections for dropdown filter
    all_creators = User.objects.filter(created_collections__isnull=False).distinct()

    creators = list(all_creators)

    # Move the current logged-in user to the front if they have created a collection
    if request.user.is_authenticated and request.user in creators:
        creators.remove(request.user)
        creators = [request.user] + creators

    context = {
        "collections": collections,
        "search_query": search_query,
        "selected_visiblity": visibility_filter,
        "creator_filter": creator_filter,
        "creators": creators,
    } | create_context(request.user)

    return render(request, "collections/collection_list.html", context)


def collection_detail(request, pk):
    """View for displaying a specific collection and its games."""
    collection = get_object_or_404(Collection, pk=pk)

    # Check if user can access this collection
    if not collection.can_user_access(request.user):
        if request.user.is_authenticated:
            messages.warning(
                request, "You don't have permission to view this private collection."
            )
            return redirect("collection_list")
        else:
            # Send unauthenticated users to a 403 forbidden
            raise PermissionDenied

    # Get games in this collection
    games = collection.games.all().order_by("title")

    # Search within collection
    search_query = request.GET.get("search", "")
    if search_query:
        games = games.filter(
            models.Q(title__icontains=search_query)
            | models.Q(description__icontains=search_query)
            | models.Q(categories__name__icontains=search_query)
        ).distinct()

    # Filter by complexity
    complexity = request.GET.get("complexity", "")
    if complexity and complexity.isdigit():
        games = games.filter(complexity=int(complexity))

    # Filter by player count
    players = request.GET.get("players", "")
    if players and players.isdigit():
        players_count = int(players)
        games = games.filter(
            min_players__lte=players_count, max_players__gte=players_count
        )

    # Filter by availability
    availability = request.GET.get("availability", "")
    if availability and availability == "available":
        games = games.filter(copies__is_available=True).distinct()

    # Get all categories for filter options
    categories = Category.objects.all().order_by("name")

    # Filter by category
    category = request.GET.get("category", "")
    if category:
        games = games.filter(categories__name=category)

    context = {
        "collection": collection,
        "games": games,
        "categories": categories,
        "search_query": search_query,
        "complexity": complexity,
        "players": players,
        "availability": availability,
        "selected_category": category,
        "is_creator": request.user == collection.creator,
    } | create_context(request.user)

    return render(request, "collections/collection_detail.html", context)


def add_collection(request):
    """View for creating a new collection."""
    if not request.user.is_authenticated:
        raise PermissionDenied

    if request.method == "POST":
        form = CollectionForm(request.POST, user=request.user)
        if form.is_valid():
            collection = form.save(commit=False)
            collection.creator = request.user

            # Enforce patron collections to be public
            if not request.user.is_librarian():
                collection.visibility = "public"  # even if they manually enter private

            collection.save()
            form.save_m2m()

            # Add selected games
            for game_id in request.POST.getlist("games"):
                game = get_object_or_404(BoardGame, id=game_id)

                # Remove game from all public collections first if adding to a priv collection
                if collection.visibility == "private":
                    public_collections = game.collections.filter(visibility="public")
                    for public_collection in public_collections:
                        public_collection.games.remove(game)

                if collection.can_add_game(game):
                    collection.games.add(game)

            messages.success(
                request, f"Collection '{collection.title}' created successfully!"
            )
            return redirect("collection_detail", pk=collection.pk)
    else:
        form = CollectionForm(user=request.user)

    # Get available games based on user type
    available_games = (
        BoardGame.objects.filter(
            models.Q(collections__isnull=True)
            | models.Q(collections__visibility="public")
        )
        .distinct()
        .order_by("title")
    )

    context = {
        "form": form,
        "available_games": available_games,
        "action": "Create",
    } | create_context(request.user)

    return render(request, "collections/collection_form.html", context)


def edit_collection(request, pk):
    """View for editing an existing collection."""
    if not request.user.is_authenticated:
        raise PermissionDenied

    collection = get_object_or_404(Collection, pk=pk)

    # Only creator or librarians can edit
    if request.user != collection.creator and not request.user.is_librarian():
        messages.error(request, "You don't have permission to edit this collection.")
        return redirect("collection_detail", pk=collection.pk)

    if request.method == "POST":
        form = CollectionForm(request.POST, instance=collection, user=request.user)
        if form.is_valid():
            # Save basic info
            collection = form.save(commit=False)

            # Enforce patron collections to be public
            if request.user.is_patron() and not request.user.is_librarian():
                collection.visibility = "public"

            collection.save()
            form.save_m2m()

            # Update games
            collection.games.clear()
            for game_id in request.POST.getlist("games"):
                game = get_object_or_404(BoardGame, id=game_id)

                # Remove game from all public collections
                if collection.visibility == "private":
                    public_collections = game.collections.filter(visibility="public")
                    for public_collection in public_collections:
                        public_collection.games.remove(game)

                collection.games.add(game)

            messages.success(
                request, f"Collection '{collection.title}' updated successfully!"
            )
            return redirect("collection_detail", pk=collection.pk)
    else:
        form = CollectionForm(instance=collection, user=request.user)

    # Get available games
    available_games = (
        BoardGame.objects.filter(
            models.Q(collections__isnull=True)
            | models.Q(collections__visibility="public")
            | models.Q(
                collections=collection
            )  # include games from this collection regardless of visibility
        )
        .distinct()
        .order_by("title")
    )

    context = {
        "form": form,
        "collection": collection,
        "available_games": available_games,
        "selected_games": collection.games.all(),
        "action": "Edit",
    } | create_context(request.user)

    return render(request, "collections/collection_form.html", context)


@require_POST
def delete_collection(request, pk):
    """View for deleting a collection."""
    if not request.user.is_authenticated:
        raise PermissionDenied

    collection = get_object_or_404(Collection, pk=pk)

    # Only creator or librarians can delete
    if request.user != collection.creator and not request.user.is_librarian():
        messages.error(request, "You don't have permission to delete this collection.")
        return redirect("collection_detail", pk=collection.pk)

    title = collection.title
    collection.delete()
    messages.success(request, f"Collection '{title}' has been deleted.")

    return redirect("collection_list")


@require_POST
def request_collection_access(request, pk):
    """View for patrons to request access to a private collection."""
    if not request.user.is_authenticated:
        raise PermissionDenied

    collection = get_object_or_404(Collection, pk=pk)

    # 1) Ensure collection is private
    if collection.visibility != "private":
        messages.error(request, "This collection is already public.")
        return redirect("collection_list")

    # 2) Check if there's already a pending request from this user for this collection
    existing_request = CollectionAccessRequest.objects.filter(
        user=request.user,
        collection=collection,
        status="pending",
    ).exists()
    if existing_request:
        messages.warning(
            request, "You already have a pending access request for this collection."
        )
        return redirect("collection_detail", pk=pk)

    # 3) Check if the user already has access (either authorized or creator)
    if (
        collection.authorized_users.filter(pk=request.user.pk).exists()
        or collection.creator == request.user
    ):
        messages.info(request, "You already have access to this collection.")
        return redirect("collection_detail", pk=pk)

    # 4) Otherwise create a new pending CollectionAccessRequest
    CollectionAccessRequest.objects.create(
        user=request.user, collection=collection, status="pending"
    )
    messages.success(
        request,
        f"Access request for '{collection.title}' has been submitted to the librarians.",
    )

    # Redirect to the collection detail page (or any other page you prefer)
    return redirect("collection_list")


def request_borrow_game(request, pk):
    if not request.user.is_authenticated or not request.user.is_patron:
        messages.error(request, "You must be a patron to request a borrow.")
        return redirect("board_game_detail", pk=pk)

    game = get_object_or_404(BoardGame, pk=pk)

    # Check if there's already a pending request for this user and this game.
    existing_request = BorrowRequest.objects.filter(
        user=request.user, game=game, status="pending"
    ).exists()

    if existing_request:
        messages.warning(
            request, "You already have a pending borrow request for this game."
        )
        return redirect("board_game_detail", pk=pk)

    # Otherwise create a new request
    BorrowRequest.objects.create(user=request.user, game=game)
    messages.success(request, "Borrow request submitted!")
    return redirect("board_game_detail", pk=pk)


def borrow_game(request, pk):
    """View for patrons to borrow a board game."""
    # Only patrons can borrow games
    if not request.user.is_patron():
        messages.error(request, "Only patrons can borrow games.")
        return redirect("board_game_catalogue")

    # Get the board game
    game = get_object_or_404(BoardGame, pk=pk)

    # Check if the game is available
    if not game.is_available:
        messages.error(
            request, f"Sorry, '{game.title}' is currently not available for borrowing."
        )
        return redirect("board_game_detail", pk=pk)

    # Check if user has reached the maximum borrowing limit (3 games)
    active_loans_count = GameLoan.objects.filter(
        user=request.user, returned=False
    ).count()

    if active_loans_count >= 3:
        messages.error(
            request,
            "You have reached the maximum limit of 3 borrowed games. Please return a game before borrowing another.",
        )
        return redirect("board_game_detail", pk=pk)

    # Find an available copy of the game
    available_copy = GameCopy.objects.filter(game=game, is_available=True).first()

    if not available_copy:
        messages.error(
            request, f"Sorry, all copies of '{game.title}' are currently borrowed."
        )
        return redirect("board_game_detail", pk=pk)

    # Create a new loan
    due_date = timezone.now() + timedelta(days=14)  # 2 weeks loan period

    GameLoan.objects.create(
        user=request.user, game_copy=available_copy, due_date=due_date
    )

    # The save method in GameLoan will update the copy's availability
    messages.success(
        request,
        f"You have successfully borrowed '{game.title}'. It is due back by {due_date.strftime('%B %d, %Y')}.",
    )
    return redirect("profile", pk=request.user.pk)


def return_game(request, pk):
    """View for patrons to return a borrowed board game."""
    # Get the loan or return 404 if not found
    loan = get_object_or_404(GameLoan, pk=pk, user=request.user, returned=False)

    if request.method == "POST":
        # Mark the loan as returned
        loan.returned = True
        loan.returned_on = timezone.now()
        loan.status = "returned"
        loan.save()

        # Update game copy availability
        game_copy = loan.game_copy
        game_copy.is_available = True
        game_copy.save()

        messages.success(
            request, f"You have successfully returned '{loan.game_copy.game.title}'."
        )
        return redirect("profile", pk=request.user.pk)

    # If GET request, show confirmation page
    context = {
        "loan": loan,
    } | create_context(request.user)

    return render(request, "users/return_game_confirm.html", context)


def manage_requests(request):
    if not is_librarian(request.user):
        raise PermissionDenied

    auth_context = create_context(request.user)

    # Fetch all PENDING requests:
    borrow_requests = BorrowRequest.objects.filter(status="pending")
    collection_access_requests = CollectionAccessRequest.objects.filter(
        status="pending"
    )

    if request.method == "POST":
        # 'request_type': 'borrow' or 'collection'
        # 'request_id': 123
        # 'action': 'approve' or 'deny'
        request_type = request.POST.get("request_type")
        request_id = request.POST.get("request_id")
        action = request.POST.get("action")

        if request_type == "borrow":
            br = get_object_or_404(BorrowRequest, id=request_id)
            if action == "approve":
                # Before setting status to 'Approved', actually borrow the game
                game = br.game
                user = br.user

                # Optional check: Does user have fewer than 3 active loans?
                active_loans_count = GameLoan.objects.filter(
                    user=user, returned=False
                ).count()
                if active_loans_count >= 3:
                    # Deny if they've reached max borrowed games
                    br.status = "Denied"
                    br.save()
                    messages.error(
                        request,
                        f"User {user.get_full_name()} has reached the max borrowing limit (3). Request denied.",
                    )
                else:
                    # Check if there's an available copy
                    available_copy = GameCopy.objects.filter(
                        game=game, is_available=True
                    ).first()
                    if not available_copy:
                        br.status = "Denied"
                        br.save()
                        messages.error(
                            request,
                            f"No available copies of '{game.title}'. Request denied.",
                        )
                    else:
                        # Create a new loan
                        due_date = timezone.now() + timedelta(days=14)  # 2-week loan
                        GameLoan.objects.create(
                            user=user,
                            game_copy=available_copy,
                            due_date=due_date,
                        )
                        # Mark the request as approved
                        br.status = "Approved"
                        br.save()
                        messages.success(
                            request,
                            f"Borrow request for '{game.title}' approved. Loan created for {user.get_full_name()}.",
                        )

            elif action == "deny":
                br.status = "Denied"
                br.save()

        elif request_type == "collection":
            cr = get_object_or_404(CollectionAccessRequest, id=request_id)
            if action == "approve":
                # Mark the request as approved
                cr.status = "Approved"
                cr.save()

                # Add the requesting user to the collection's authorized_users
                # (only if they're not already authorized)
                if not cr.collection.authorized_users.filter(pk=cr.user.pk).exists():
                    cr.collection.authorized_users.add(cr.user)

                messages.success(
                    request,
                    f"Collection access for '{cr.collection.title}' approved for {cr.user.get_full_name()}.",
                )
            elif action == "deny":
                cr.status = "Denied"
                cr.save()
                messages.success(
                    request,
                    f"Collection access for '{cr.collection.title}' denied for {cr.user.get_full_name()}.",
                )

            return redirect("manage_requests")

    context = {
        "borrow_requests": borrow_requests,
        "collection_requests": collection_access_requests,
    } | auth_context

    return render(request, "users/request_management.html", context)


@require_POST
def add_review(request, pk):
    """Add review endpoint."""
    game = get_object_or_404(BoardGame, pk=pk)
    rating = request.POST.get("rating")
    title = request.POST.get("title", "")
    comment = request.POST.get("comment", "")

    # Check if the review already exists
    existing_review = Review.objects.filter(user=request.user, game=game).first()

    if existing_review:
        # Option 1: Update the existing review
        existing_review.rating = rating
        existing_review.title = title
        existing_review.comment = comment
        existing_review.save()
        messages.success(request, "Your review has been updated.")
    else:
        # Option 2: Create a new review if one does not exist
        Review.objects.create(
            user=request.user,
            game=game,
            rating=rating,
            title=title,
            comment=comment,
        )
        messages.success(request, "Your review has been added.")

    # Redirect back to the game detail page
    return HttpResponseRedirect(reverse("board_game_detail", args=[pk]))


def manage_librarians(request):
    """Page for librarians to see all non-librarian users and promote them to librarian."""
    if not is_librarian(request.user):
        raise PermissionDenied

    # Get the 'Librarian' group
    librarian_group, _ = Group.objects.get_or_create(name="Librarian")
    # All users who are *not* in the Librarian group
    non_librarians = User.objects.exclude(groups=librarian_group)

    context = {
        "users": non_librarians,
    } | create_context(request.user)

    return render(request, "users/promote_users.html", context)


@require_POST
def promote_to_librarian(request, pk):
    """Handle the POST request to promote a single user to the Librarian group."""
    if not is_librarian(request.user):
        raise PermissionDenied

    user_to_promote = get_object_or_404(User, pk=pk)
    librarian_group, _ = Group.objects.get_or_create(name="Librarian")

    # Add user to the Librarian group
    user_to_promote.groups.add(librarian_group)
    # You could also set user_to_promote.is_staff = True if desired,
    # but that depends on your workflow.
    user_to_promote.save()

    messages.success(
        request,
        f"User '{user_to_promote.get_full_name() or user_to_promote.email}' "
        "has been promoted to Librarian.",
    )
    return redirect("manage_librarians")
