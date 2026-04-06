from decimal import Decimal
from django.core.files import File
import torch
from django.core.paginator import Paginator
from django.db.models import Prefetch
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate,login,logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.core.mail import send_mail
from django.contrib.auth.models import User
from .models import EmailVerification,Searched, Course,Comments,Reply, EpisodeProgress,Wallet,SendSession,ExportSession, ProposalEpisode, Proposal, Vote, Start_course,Complete_course, UserProfile, Episode, ChatMessage, ConvoSummary, Temp_quizscore, Subscribe
import random
import string
from django.http import JsonResponse,FileResponse, Http404
from django.views.decorators.csrf import csrf_exempt
import json, time
from sentence_transformers import SentenceTransformer, util
from .Ai import transcribe, validate_content, save_uploaded_to_temp, generate_summary, Assisant_reply,quiz
from .Blockchain import generate_certificate,check_subscription,certificate_ipfs,certificate_metadata,sign_certificate_message,mint_certificate_custodial,verify_minter_address,check_eth_balance, send_eth,send_usdc, decrypt_private_key, create_wallet_for_new_user, encrypt_private_key, connect_wallet, check_usdc_balance, direct_usdc_transfer
import os
from datetime import timedelta
from django.utils import timezone
from django_ratelimit.decorators import ratelimit


model = SentenceTransformer('all-MiniLM-L6-v2')


# Create your views here.
def home(request):
    
    return render(request, 'home.html')

def register(request):
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == 'POST':
        email = request.POST.get('email')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        first_name = request.POST.get('first_name', '')
        last_name = request.POST.get('last_name', '')
        if password1 == password2:
            try:
                # Check if email is already registered
                if User.objects.filter(email=email).exists():
                    messages.error(request, "This email is already registered.")
                    return redirect('login')
                # Check for existing verification code
                try:
                    verification = EmailVerification.objects.get(email=email)
                    if not verification.is_expired():
                        messages.error(request, "A verification code was already sent. Check your email.")
                        return redirect('verify_email')
                    else:
                        verification.delete()  # Remove expired code
                except EmailVerification.DoesNotExist:
                    pass
                # Generate 6-digit code
                code = ''.join(random.choices(string.digits, k=6))
                expires_at = timezone.now() + timedelta(minutes=10)
                EmailVerification.objects.create(
                    email=email,
                    code=code,
                    expires_at=expires_at
                )
                # Send email
                send_mail(
                    'Verify Your Email',
                    f'Your verification code is: {code}',
                    settings.EMAIL_HOST_USER,
                    [email],
                    fail_silently=False,
                )
                # Store registration data in session
                request.session['registration_data'] = {
                    'email': email,
                    'password': password1,
                    'first_name': first_name,
                    'last_name': last_name
                }
                messages.success(request, "Verification code sent to your email.")
                return redirect('verify_email')
            except Exception as e:
                messages.error(request, f"Error sending verification code: {str(e)}")
                return redirect('register')
        else:
            messages.error(request, "ensure that the passwords are the same.")
    return render(request, 'register.html')


def verify_email(request):
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == 'POST':
        code = request.POST.get('code')
        registration_data = request.session.get('registration_data')
        if not registration_data:
            messages.error(request, "Session expired. Please start registration again.")
            return redirect('register')
        email = registration_data.get('email')
        try:
            verification = EmailVerification.objects.get(email=email, code=code)
            if verification.is_expired():
                messages.error(request, "Verification code expired. Please request a new one.")
                verification.delete()
                return redirect('register')
            # Create user
            user = User.objects.create(
                username=email,
                email=email,
                first_name=registration_data.get('first_name', ''),
                last_name=registration_data.get('last_name', '')
            )
            user.set_password(registration_data.get('password'))
            user.save()
            create_wallet_for_new_user(user)
            verification.delete()
            del request.session['registration_data']
            # Log in user with specified backend
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            messages.success(request, f"Welcome, {user.first_name}!")
            return redirect('dashboard')
        except EmailVerification.DoesNotExist:
            messages.error(request, "Invalid verification code.")
            return redirect('verify_email')
        except Exception as e:
            messages.error(request, f"Error: {str(e)}")
            return redirect('verify_email')
    return render(request, 'verify_email.html')

@ratelimit(key='ip', rate='10/h', block=False)
@ratelimit(key='post:email', rate='10/h', block=False)
@ratelimit(key='post:username', rate='10/h', block=False)
def login_view(request):
    was_limited = getattr(request, 'limited', False)
    if was_limited:
        messages.warning(request, "Too many login attempt. Please wait an hour and try again.")
        return redirect(request.META.get('HTTP_REFERER', '/'))
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == 'POST':
        identifier = request.POST['identifier']
        password = request.POST['password']
        remember_me = request.POST.get('remember_me', '')

        if "@" in identifier:
            try:
                user_obj = User.objects.get(email=identifier)
                username = user_obj.username
            except User.DoesNotExist:
                username = None
        else:
            username = identifier
        if username:
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                if remember_me:
                    request.session.set_expiry(1209600)
                messages.success(request, 'Login successful!')
                return redirect('dashboard')  # Redirect to your home page
            else:
                messages.error(request, 'Invalid password')
        else:
            messages.error(request, 'Email/username not in database')
    return render(request, 'login.html')

def forget_password(request):
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == 'POST':
        email = request.POST['email']
        user = User.objects.filter(email=email).first()
        if user:
            chars = string.ascii_letters + string.digits + "!@#$%^&*()_+[]{}|;:,.<>?"
            password = ''.join(random.choice(chars) for _ in range(8))
            send_mail(
                'Password Reset',
                f'Your new password is : {password} \nIt is best practice to copy the password and paste in the login page',
                settings.EMAIL_HOST_USER,
                [email],
                fail_silently=False,
            )
            user.set_password(password)
            user.save()

            messages.success(request, 'Password reset successful!')
            return redirect('login')
        else:
            messages.error(request, 'Email not found, please Register')
    return render(request, 'forget_password.html')

@login_required()
def dashboard(request):
    if request.user.is_authenticated:
        user = request.user
        check_subscription(user)
        courses = Course.objects.filter(creator=user).first()
        started_course = Start_course.objects.filter(student=user).all()
        completed_course = Complete_course.objects.filter(student=user).all()
        ongoing_courses = started_course.exclude(course__in=completed_course.values_list('course', flat=True))
        return render(request, 'dashboard.html', {'user':user,
                                                  'courses':courses,
                                                  'started_course':started_course,
                                                  'completed_course':completed_course,
                                                  'ongoing_course':ongoing_courses})
    return redirect('login')

@login_required
def update_profile_image(request):
    if request.method == 'POST' and request.FILES.get('image'):
        profile, created = UserProfile.objects.get_or_create(user=request.user)
        profile.image = request.FILES["image"]
        profile.save()
    return redirect(request.META.get('HTTP_REFERER', 'dashboard'))


@login_required()
def edit_profile(request):
    if request.user.is_authenticated:
        user = request.user

        if request.method == 'POST':
            user.username = request.POST.get('username')
            user.first_name = request.POST.get('first_name')
            user.last_name = request.POST.get('last_name')
            user.email = request.POST.get('email')
            user.save()
            return redirect('dashboard')

        return render(request, 'edit_profile.html', {'user': user})

    return redirect('login')

@login_required
def change_password(request):
    user = request.user
    if request.method == 'POST':
        old_pass = request.POST.get('old_password')
        new_pass1 = request.POST.get('new_password1')
        new_pass2 = request.POST.get('new_password2')
        if not user.check_password(old_pass):
            messages.error(request, 'Your old password do not match your current password.')
            return redirect('change_password')

        if old_pass == new_pass1:
            messages.error(request, 'Old password and new password must not match')
            return redirect('change_password')

        if new_pass1 == new_pass2:
            user.set_password(new_pass1)
            user.save()
            messages.success(request, 'You have successfully changed your password, Please re-login')
            return redirect('dashboard')
        else:
            messages.error(request, 'new password and confirm password must match')

    return render( request, 'change_password.html')


@login_required()
def dao(request):
    if not check_subscription(request.user):
        messages.error(request, 'Your subscription is either expired or you havent subscribed yet')
        return redirect('subscribe')
    proposals = Proposal.objects.all().order_by('-created_at')
    return render(request, 'dao.html', {'proposals':proposals})

@login_required
def proposal_detail(request, proposal_id):
    if not check_subscription(request.user):
        messages.error(request, 'Your subscription is either expired or you havent subscribed yet')
        return redirect('subscribe')
    proposal = get_object_or_404(Proposal, id=proposal_id)
    user = request.user

    if request.method == "POST":
        vote_type = request.POST.get("vote_type")

        if not user.is_authenticated:
            messages.warning(request, "You need to log in to vote.")
            return redirect("login")

        # Check if user already voted
        vote, created = Vote.objects.get_or_create(
            user=user,
            proposal=proposal,
            defaults={"vote_type": vote_type},
        )

        if not created:
            messages.info(request, "You’ve already voted on this proposal.")
            return redirect("proposal_detail", proposal_id=proposal.id)

        # Update proposal vote count
        if vote_type == "up":
            proposal.up_votes += 1
        elif vote_type == "down":
            proposal.down_votes += 1
        proposal.save()

        messages.success(request, "Your vote has been recorded!")
        return redirect("proposal_detail", proposal_id=proposal.id)

    # Check if user has already voted
    user_voted = False
    if user.is_authenticated:
        user_voted = Vote.objects.filter(user=user, proposal=proposal).exists()

    return render(request, "proposal_detail.html", {
        "proposal": proposal,
        "user_voted": user_voted,
    })

@login_required()
def user_course(request):
    user = request.user
    courses = Course.objects.filter(creator=user)
    paginator = Paginator(courses, 8)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'user_course.html',{'courses':page_obj,
                                               'is_paginated': page_obj.has_other_pages(),
                                               'page_obj': page_obj,
                                               })

def about(request):
    return render(request, 'about.html')

def logout_view(request):
    logout(request)
    return redirect('home')

@login_required()
def courses(request):
    courses = Course.objects.all().order_by('-created_at')
    paginator = Paginator(courses, 8)  # 8 courses per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'courses.html', {
        'courses': page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'page_obj': page_obj,
    })

@login_required
def Search(request):
    category = request.POST.get("category", "")
    query = request.POST.get("search", "")


    if category and not query:
        courses = Course.objects.filter(category=category)

    elif query :
        course = Course.objects.all()
        title = [c.title for c in course]
        if len(query)<=100:
            Searched.objects.create(user=request.user, search=query)

        embedding = [json.loads(c.embedding) for c in course]
        query_embedding = model.encode(query, convert_to_tensor=True)
        titles_embedding = torch.stack([torch.tensor(c) for c in embedding])

        similarities = util.cos_sim(query_embedding, titles_embedding)[0]

        related = [
            {"title": title[i], "score": float(similarities[i])}
            for i in range(len(title)) if similarities[i] > 0.3 ]

        related.sort(key=lambda x: x["score"], reverse=True)

        related_title=[c["title"] for c in related]

        if category:
            courses = Course.objects.filter(title__in=related_title, category=category)
        else:
            courses = Course.objects.filter(title__in=related_title)

    paginator = Paginator(courses, 8)  # 8 courses per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'courses.html', {
        'courses': page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'page_obj': page_obj,
    })



@login_required
def course_detail(request, course_id):
    if not check_subscription(request.user):
        messages.error(request, 'Your subscription is either expired or you havent subscribed yet')
        return redirect('subscribe')
    course = get_object_or_404(Course, id=course_id)
    user = request.user

    comment_list = []
    course_comments = Comments.objects.filter(course=course, episode__isnull=True)
    comment_list.extend(course_comments)

    episodes_with_progress = course.episodes.prefetch_related(
        Prefetch(
            'ep_progress',  # <- matches related_name in EpisodeProgress
            queryset=EpisodeProgress.objects.filter(user=request.user),
            to_attr='user_progress'  # stores results in a list: episode.user_progress
        )
    )
    started_course = Start_course.objects.filter(student=user, course=course).first()
    return render(request, 'course_detail.html', {'course':course,
                                                  'user':user,
                                                  'started_course':started_course,
                                                  'episodes': episodes_with_progress,
                                                  'comments':comment_list,
                                                  })
@login_required
def start_course(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    user = request.user
    start = Start_course.objects.filter(course=course, student=user).first()
    if start:
        messages.error(request, 'You have started this course')
        return redirect('course_detail', course_id)

    Start_course.objects.create(course=course, student=user)

    return redirect('course_detail', course_id)


@login_required
def complete_course(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    user = request.user
    acct = connect_wallet(user)
    temp_C = Temp_quizscore.objects.filter(user=user, course=course).first()
    completed = Complete_course.objects.filter(course=course,student=user).first()
    if completed:
        messages.error(request, 'You have already completed this course')
        return redirect('course_detail', course_id)
    if not temp_C:
        messages.error(request, "You must complete the quiz first.")
        return redirect('quiz_view', course_id)
    if not user.first_name and not user.last_name:
        messages.error(request, "please add a first name and a last name, in your profile")
        return redirect('edit_profile')

    pre_certificate = generate_certificate(name=f"{user.first_name} {user.last_name}",
                                       course=f"{course.title}",
                                       cert_id=f"course_id_{course_id}",
                                       score=int(temp_C.score),
                                       output_path=f"pre_Certificate_course_{course_id}_user_{user.id}.png")
    store_image = certificate_ipfs(pre_certificate)
    store_metadata = certificate_metadata(acct.address,course.title,course_id,store_image)
    signature = sign_certificate_message(acct.address,course_id,f"ipfs://{store_metadata}")
    mint = mint_certificate_custodial(acct,course_id,f'ipfs://{store_metadata}',signature)
    os.remove(pre_certificate)
    if 'error' in mint:
        messages.error(request, f"Mint failed: {mint['error']}")
        return redirect('course_detail', course_id)
    if mint['token_id']:
        certificate = generate_certificate(name=f"{user.first_name} {user.last_name}".title(),
                                               course=f"{course.title.upper()}",
                                               cert_id=mint['token_id'],
                                               score=int(temp_C.score),
                                               output_path=f"Certificate_course_{course_id}_user_{user.id}.png",
                                               txhash=mint['tx_hash'])
        with open(certificate, "rb") as f:
            django_file = File(f)
            Complete_course.objects.create(
                course=course,
                student=user,
                certificate_image=django_file,
                score=int(temp_C.score),
                tx_hash=mint['tx_hash'],
                token_id=mint['token_id']
            )

    else:
        messages.error(request,f'This transaction reverted because this user might have already minted this course, if this is not true contact us on Discord, here is you tx_hash:{mint["tx_hash"]}')
        return redirect('dashboard')
    os.remove(certificate)

    messages.success(request, f'Congratulation on minting this certificate\nTransaction_hash:{mint["tx_hash"]}')
    return redirect('course_detail', course_id)

@login_required
def episode_view(request, course_id, episode_id):
    if not check_subscription(request.user):
        messages.error(request, 'Your subscription is either expired or you havent subscribed yet')
        return redirect('subscribe')
    course = get_object_or_404(Course, id=course_id)
    episodes = list(course.episodes.all().order_by('id'))
    episode = get_object_or_404(course.episodes, id=episode_id)
    completed_course = Complete_course.objects.filter(student=request.user, course=course).first()

    progress, created = EpisodeProgress.objects.get_or_create(
        user=request.user, course=course, episode=episode
    )

    comment_list = []
    course_comments = Comments.objects.filter(course=course, episode=episode)
    comment_list.extend(course_comments)
    # Find current position
    current_index = episodes.index(episode)
    next_episode = episodes[current_index + 1] if current_index + 1 < len(episodes) else None
    prev_episode = episodes[current_index - 1] if current_index - 1 >= 0 else None
    last_episode = episodes[current_index] if current_index + 1 == len(episodes) else None

    return render(request, 'episode_view.html', {
        'course': course,
        'episode': episode,
        'episodes': episodes,
        'next_episode': next_episode,
        'prev_episode': prev_episode,
        'last_episode' : last_episode,
        'progress': progress,
        'completed_course':completed_course,
        'comments':comment_list,
        'user':request.user
    })

@login_required
def rewatch(request, course_id, episode_id):
    course = get_object_or_404(Course, id=course_id)
    episode = get_object_or_404(Episode, id=episode_id, course=course)
    if episode.video:
        progress = get_object_or_404(EpisodeProgress, user=request.user, course=course, episode=episode)
        if progress.progress >=100:
            progress.watched_count +=1
            progress.progress = 0
            progress.save()
            return redirect('episode_view', course_id, episode_id)
    return redirect('episode_view', course_id, episode_id)



@csrf_exempt
@login_required
def save_progress(request, course_id, episode_id):
    """AJAX endpoint to save or update progress"""
    if request.method == "POST":
        data = json.loads(request.body)
        progress, _ = EpisodeProgress.objects.get_or_create(
            user=request.user,
            course_id=course_id,
            episode_id=episode_id
        )
        progress.progress = data.get("progress", 0)
        progress.last_position = data.get("last_position", 0)
        progress.completed = data.get("completed", False)
        progress.save()
        return JsonResponse({"status": "ok"})
    return JsonResponse({"status": "error"}, status=400)


@login_required
def toggle_complete(request, course_id, episode_id):
    """Toggle completion status manually"""
    progress, _ = EpisodeProgress.objects.get_or_create(
        user=request.user,
        course_id=course_id,
        episode_id=episode_id
    )
    progress.completed = not progress.completed
    progress.progress = 100.0 if progress.completed else 0.0
    progress.save()
    return JsonResponse({"completed": progress.completed})


@login_required
def add_course(request):
    if not check_subscription(request.user):
        messages.error(request, 'Your subscription is either expired or you havent subscribed yet')
        return redirect('subscribe')
    if request.method == 'POST':

        # -------------------------
        # 1. Basic Course Data
        # -------------------------
        course_title = request.POST.get('course_title')
        description = request.POST.get('course_description')
        cover_image = request.FILES.get('cover_image')
        category = request.POST.get('category')

        proposal = Proposal.objects.create(
            proposer=request.user,
            title=course_title,
            description=description,
            cover_image=cover_image,
            identifier='course',
            category=category
        )

        # -------------------------
        # 2. Capture Episode Inputs
        # -------------------------
        titles = request.POST.getlist('episode_title[]')
        descriptions = request.POST.getlist('episode_description[]')
        videos = request.FILES.getlist('episode_video[]')

        # Max count ensures safe looping
        episodes_count = max(len(titles), len(descriptions), len(videos))

        score_list = []
        episode_saved = 0

        # -------------------------
        # 3. Episode Loop
        # -------------------------
        for i in range(episodes_count):

            title = titles[i].strip() if i < len(titles) else ""
            desc = descriptions[i].strip() if i < len(descriptions) else ""
            video = videos[i] if i < len(videos) else None

            # Skip empty titles entirely
            if not title:
                continue

            # ---------------------------------------
            # CASE A: Episode has NO VIDEO
            # ---------------------------------------
            if video is None:
                ProposalEpisode.objects.create(
                    proposal=proposal,
                    title=title,
                    description=desc,
                    video=None,
                    transcript=desc,
                    score=0
                )
                messages.warning(
                    request,
                    f"Episode {i+1} saved without video — text-only episode."
                )
                episode_saved += 1
                continue

            # ---------------------------------------
            # CASE B: Episode HAS VIDEO
            # ---------------------------------------
            try:

                # 1. Transcribe
                temp_path = save_uploaded_to_temp(video)


                transcript = transcribe(temp_path)

                os.remove(temp_path)
                # 2. Validate content
                validate = validate_content(
                    course_title, description,
                    title, desc,
                    transcript
                )

                # 3. Validation checks

                if validate["relevance_score"] < 70:
                    messages.error(
                        request,
                        f"Episode {i + 1} relevance score too low "
                        f"({validate['relevance_score']}).\n"
                        f"{validate['explanation']}"
                    )
                    continue

                if not validate["matches"]:
                    messages.error(
                        request,
                        f"Episode {i+1} video does not match the course topic. "
                        f"Suggested title: {validate['better_title']}"
                    )
                    continue

                # ---------------------------------------
                # Episode is valid → Save
                # ---------------------------------------
                ProposalEpisode.objects.create(
                    proposal=proposal,
                    title=title,
                    description=desc,
                    video=video,
                    transcript=transcript,
                    score=validate["relevance_score"]
                )

                score_list.append(validate["relevance_score"])
                episode_saved += 1

            except Exception as e:
                messages.error(
                    request,
                    f"AI processing failed for episode {i+1}. Error: {str(e)}"
                )
                continue

        # -------------------------
        # 4. Final Checks
        # -------------------------
        if episode_saved == 0:
            messages.error(request, "Course submission failed: Add atleast one episode.")
            proposal.delete()  # Prevent dead proposals
            return redirect('add_course')

        # Compute score safely
        proposal.score = sum(score_list) / len(score_list) if score_list else 70
        proposal.save()

        messages.success(
            request,
            "Course proposal submitted! It will be reviewed within 24 hours."
        )
        return redirect('dao')

    return render(request, 'add_course.html')



@login_required
def edit_course(request, course_id):
    if not check_subscription(request.user):
        messages.error(request, 'Your subscription is either expired or you havent subscribed yet')
        return redirect('subscribe')
    course = get_object_or_404(Course, id=course_id)
    episodes = list(course.episodes.all())

    if request.method == 'POST':

        # ----------------------------
        # 1. UPDATE COURSE INFO
        # ----------------------------
        new_title = request.POST.get('course_title', '').strip()
        new_description = request.POST.get('course_description', '').strip()

        if new_title:
            course.title = new_title
            course.embedding = json.dumps(model.encode(new_title).tolist())

        course.description = new_description

        cover_image = request.FILES.get('cover_image')
        if cover_image:
            course.cover_image = cover_image

        course.save()

        # ----------------------------
        # 2. HANDLE EPISODES
        # ----------------------------
        episode_titles = request.POST.getlist('episode_title[]') or []
        episode_descriptions = request.POST.getlist('episode_description[]') or []

        for i, title in enumerate(episode_titles):

            title = title.strip()
            if not title:
                continue  # skip empty episode rows

            # Get existing or create new
            if i < len(episodes):
                episode = episodes[i]
            else:
                episode = Episode(course=course)

            # Update titles & descriptions
            episode.title = title
            episode.description = (
                episode_descriptions[i].strip()
                if i < len(episode_descriptions)
                else ''
            )

            # ----------------------------
            # 3. VIDEO VALIDATION (only if a new video was uploaded)
            # ----------------------------
            uploaded_video = request.FILES.get(f'episode_video_{i}')

            if uploaded_video:
                try:
                    temp_path = save_uploaded_to_temp(uploaded_video)


                    transcript = transcribe(temp_path)

                    os.remove(temp_path)

                    validate = validate_content(
                        new_title,
                        new_description,
                        title,
                        episode.description,
                        transcript
                    )

                    if validate["relevance_score"] < 70:
                        messages.error(
                            request,
                            f"Episode {i+1} relevance score too low "
                            f"({validate['relevance_score']}).\n"
                            f"{validate['explanation']}"
                        )
                        continue

                    if not validate["matches"]:
                        messages.error(
                            request,
                            f"Episode {i+1} video does not match topic. "
                            f"Suggested title: {validate['better_title']}"
                        )
                        continue

                    # Valid video
                    episode.video = uploaded_video
                    episode.transcript = transcript
                    episode.score = validate["relevance_score"]

                except Exception as e:
                    messages.error(
                        request,
                        f"AI processing failed for episode {i+1}. Error: {str(e)}"
                    )
                    continue

            episode.save()

        # ----------------------------
        # 4. DELETE REMOVED EPISODES
        # ----------------------------
        if len(episode_titles) < len(episodes):
            for e in episodes[len(episode_titles):]:
                e.delete()

        # ----------------------------
        # 5. UPDATE COURSE OVERALL SCORE
        # ----------------------------
        all_scores = course.episodes.values_list("score", flat=True)
        valid_scores = [s for s in all_scores if s and s > 0]

        course.score = sum(valid_scores) / len(valid_scores) if valid_scores else 70
        course.save()

        messages.success(request, "Course updated successfully!")
        return redirect('course_detail', course_id)

    return render(request, "edit_course.html", {
        "course": course,
        "episodes": episodes,
    })


@login_required
def add_proposal(request):
    if not check_subscription(request.user):
        messages.error(request, 'Your subscription is either expired or you havent subscribed yet')
        return redirect('subscribe')
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description')

        # Create a new proposal
        Proposal.objects.create(
            proposer =request.user,
            title=title,
            description=description,
            identifier='case'  # or 'course' depending on how you want to classify user proposals
        )
        return redirect('dao')
    return render(request, 'add_proposal.html')

@ratelimit(key='user', rate='30/d', block=False)
@login_required
def send_message(request):
    was_limited = getattr(request, 'limited', False)
    if was_limited:
        messages.warning(request, "You have exceeded chat message limit of the day.")
        return redirect(request.META.get('HTTP_REFERER', '/'))

    user = request.user
    user_msg = request.POST.get("message")

    # 1. Save user's message
    ChatMessage.objects.create(
        user=user,
        role="user",
        content=user_msg
    )

    # === FETCH SUMMARY ===
    summary_obj = ConvoSummary.objects.filter(user=user).first()
    current_summary = summary_obj.content if summary_obj else ""

    # === FETCH LAST 10 MESSAGES ===
    last_messages_qs = ChatMessage.objects.filter(user=user).order_by('-timestamp')[:10]
    last_messages = list(reversed(last_messages_qs))  # convert to list to reuse



    assistant_reply = Assisant_reply(user=user,summary=current_summary, last_messages=last_messages)
    # 4. Save AI reply
    ChatMessage.objects.create(
        user=user,
        role="assistant",
        content=assistant_reply
    )

    # === SUMMARY UPDATE LOGIC ===
    total_messages = ChatMessage.objects.filter(user=user).count()

    if total_messages % 10 == 0:

        # Fetch the LAST 10 again (fresh copy)
        summary_messages_qs = ChatMessage.objects.filter(user=user).order_by('-timestamp')[:10]
        summary_messages = list(reversed(summary_messages_qs))

        # Generate new summary
        updated_summary = generate_summary(
            current=current_summary,
            last_messages=summary_messages
        )

        # Save summary
        if summary_obj:
            summary_obj.content = updated_summary
            summary_obj.save()
        else:
            ConvoSummary.objects.create(
                user=user,
                content=updated_summary
            )

    # Return reply
    return JsonResponse({"reply": assistant_reply})

@login_required
def Technical_quiz(request, courseid):
    if not check_subscription(request.user):
        messages.error(request, 'Your subscription is either expired or you havent subscribed yet')
        return redirect('subscribe')
    course = get_object_or_404(Course, id=courseid)

    episodes = Episode.objects.filter(course=course)
    episode_list = [ep.transcript for ep in episodes]
    quiz_list = quiz(episode_list)
    total = len(quiz_list)

    if request.method == "GET":
        request.session['quiz_answers'] = [q["Answer"] for q in quiz_list]
        request.session["quiz_total"] = total

    Temp = Temp_quizscore.objects.filter(user=request.user, course=course).first()
    if Temp:
        score = Temp.score
        passed = score>=60
    else:
        score = 0
        passed = False

    if request.method == 'POST':
        correct = 0

        correct_answers = request.session.get('quiz_answers', [])
        dtotal = request.session.get("quiz_total", 0)
        for i in range(1, dtotal + 1):
            user_answer = request.POST.get(f'answer_{i}')

            if correct_answers[i - 1] == user_answer:
                correct += 1

        score = correct / dtotal * 100
        # passed = score >= 60

        del request.session['quiz_answers']
        del request.session["quiz_total"]

        Temp_quizscore.objects.filter(user=request.user, course=course).delete()
        Temp_quizscore.objects.create(
            user=request.user,
            course=course,
            score=score
        )
        return redirect('quiz_view', courseid)

    return render(request, "Technical_quiz.html", {
        "quiz_list": quiz_list,
        "course": course,
        "score": score,
        "passed": passed
    })

@login_required
def retake(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    Temp_quizscore.objects.filter(user=request.user, course=course).delete()
    return redirect('quiz_view', course_id)



@login_required
def generate_wallet(request):
    user = request.user
    has_wallet = Wallet.objects.filter(user=user).first()
    if has_wallet:
        messages.error(request, "You already have an account ")
    else:
        create_wallet_for_new_user(user)
        messages.success(request, "wallet created successfully")
    return redirect('dashboard')

@login_required
def subscribe(request):
    user = request.user
    return render(request, 'subscribe.html', {'user':user})


@login_required
def get_subscribe(request, plan):
    user = request.user
    acct = connect_wallet(user)
    if not acct:
        messages.error(request, 'No wallet assigned to this user, dont worry the system have generated one, fund wallet and try again!')
        return redirect('generate')
    amount = 0
    duration = ""
    expire = None
    active_month = 0
    if plan == 'Y':
        amount += 20
        duration = "yearly"
        active_month +=12
        expire = timezone.now() + timedelta(days=365)

    elif plan == 'M':
        amount += 10
        duration = "monthly"
        active_month +=1
        expire = timezone.now() + timedelta(days=30)

    balance = check_usdc_balance(acct, amount)
    if balance["has_enough"]:
        result = direct_usdc_transfer(user_acct=acct, amount=amount)
        if result["success"]:
            try:
                sub = user.subscribe
            except Subscribe.DoesNotExist:
                sub = None

            if sub is None:
                # First subscription
                Subscribe.objects.create(
                    user=user,
                    duration=duration,
                    is_active=True,
                    active_months=active_month,
                    expires_at=expire
                )
            else:
                # Renew or extend
                sub.duration = duration
                sub.active_months += active_month
                sub.expires_at = expire
                sub.is_active = True
                sub.save()
            messages.success(request, 'Thank you for subscribing, Enjoy the platform')
            return redirect('courses')
        else:
            messages.error(request, f'The transaction was not successful, {result["error"]}')
            return redirect('subscribe')
    messages.error(request, f"Your wallet balance is less than {amount}")
    return redirect('wallet')

@login_required
def wallet(request):
    user = request.user
    acct = connect_wallet(user)
    balance = check_usdc_balance(acct, amount=0)
    eth_balance = check_eth_balance(acct, amount=0)

    return render(request, "wallet.html", {'acct':acct.address,
                                           'usdc_balance':balance['balance_usdc'],
                                           'eth_balance':eth_balance['balance_eth']})

@csrf_exempt
@login_required
def send_init_view(request):
    data = json.loads(request.body)

    asset = data["asset"]
    to = data["to"]
    amount = Decimal(data["amount"])
    password = data["password"]

    user = request.user

    if not user.check_password(password):
        return JsonResponse({"error": "Invalid password"}, status=401)

    acct = connect_wallet(user)
    wallet = check_usdc_balance(acct, amount)
    eth_wallet = check_eth_balance(acct, amount)
    if asset == "USDC" and not wallet['has_enough']:
        return JsonResponse({"error": "Insufficient balance"}, status=400)

    if asset == "ETH" and not eth_wallet['has_enough']:
        return JsonResponse({"error": "Insufficient balance"}, status=400)

    otp = str(random.randint(100000, 999999))

    send_session = SendSession.objects.create(
        user=user,
        asset=asset,
        to_address=to,
        amount=amount,
        otp=otp
    )
    print(f'email:{user.email}')
    send_mail(
        'Security verification',
        f'You are sending {amount}{asset}, verify your email: {otp}',
        settings.EMAIL_HOST_USER,
        [user.email],
        fail_silently=False,
    )

    return JsonResponse({
        "session_id": send_session.id,
        "message": "OTP sent"
    })

@csrf_exempt
@login_required
def send_confirm_view(request):
    try:
        data = json.loads(request.body)
        session_id = data.get("session_id")
        otp = data.get("otp")

        session = SendSession.objects.get(
            id=session_id,
            user=request.user,
            is_used=False
        )

        if session.otp != otp:
            return JsonResponse({"error": "Invalid OTP"}, status=400)

        acct = connect_wallet(request.user)

        result = (
            send_eth(acct, session.amount, session.to_address)
            if session.asset == "ETH"
            else send_usdc(acct, session.amount, session.to_address)
        )

        if not result["success"]:
            return JsonResponse({"error": result["error"]}, status=400)

        session.is_used = True
        session.save()

        return JsonResponse({"tx_hash": result["tx_hash"]})

    except SendSession.DoesNotExist:
        return JsonResponse({"error": "Invalid session"}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

@csrf_exempt
@login_required
def export_init_view(request):
    data = json.loads(request.body)
    password = data.get("password")

    user = request.user

    if not user.check_password(password):
        return JsonResponse({"error": "Invalid password"}, status=401)

    otp = str(random.randint(100000, 999999))

    session = ExportSession.objects.create(
        user=user,
        otp=otp
    )

    send_mail(
        "Wallet Export OTP",
        f"Your export OTP is {otp}",
        settings.EMAIL_HOST_USER,
        [user.email],
        fail_silently=False
    )

    return JsonResponse({
        "session_id": session.id,
        "message": "OTP sent"
    })

@csrf_exempt
@login_required
def export_confirm_view(request):
    data = json.loads(request.body)

    session_id = data.get("session_id")
    otp = data.get("otp")

    try:
        session = ExportSession.objects.get(
            id=session_id,
            user=request.user,
            is_used=False
        )
    except ExportSession.DoesNotExist:
        return JsonResponse({"error": "Invalid session"}, status=400)

    if session.otp != otp:
        return JsonResponse({"error": "Invalid OTP"}, status=401)

    # connect wallet
    acct = connect_wallet(request.user)

    session.is_used = True
    session.save()

    return JsonResponse({
        "private_key": acct.key.hex()
    })


@login_required
def reward(request):
    user = request.user
    if not check_subscription(user):
        messages.error(request, 'Your subscription is either expired or you havent subscribed yet')
        return redirect('subscribe')
    course = Course.objects.filter(creator=user).all()

    return render(request, 'reward.html', {'user':user,'course':course})

@login_required
def add_comment(request, course_id, episode_id):
    course = Course.objects.get(id=course_id)
    if request.method == 'POST':
        comment = request.POST.get('comment')
        if episode_id == 0:
            Comments.objects.create(
                user=request.user,
                course= course,
                comment = comment
            )
            return redirect('course_detail', course_id)
        else:
            episode = Episode.objects.get(id=episode_id)
            Comments.objects.create(
                user=request.user,
                course= course,
                comment = comment,
                episode = episode
            )
            return redirect('episode_view', course_id, episode_id)
    return None

@login_required
def add_reply(request, comment_id):
    comment = Comments.objects.get(id=comment_id)
    if request.method == 'POST':
        reply = request.POST.get('reply')
        Reply.objects.create(
            user=request.user,
            comment = comment,
            reply = reply
        )

    if comment.episode:
        return redirect('episode_view', comment.course.id, comment.episode.id)
    else:
        return redirect('course_detail', comment.course.id)



@login_required
def download_certificate_image(request, cert_id):
    Certificate = Complete_course.objects.get(id=cert_id, student=request.user)

    if not Certificate.certificate_image:
        raise Http404("No image")

    response = FileResponse(Certificate.certificate_image.open("rb"), as_attachment=True)
    response["Content-Type"] = "application/octet-stream"
    response["Content-Disposition"] = f'attachment; filename="{Certificate.certificate_image.name.split("/")[-1]}"'
    return response