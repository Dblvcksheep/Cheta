from datetime import timedelta
from decimal import Decimal
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User


# Create your models here.
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    image = models.ImageField(upload_to="avatars/", blank=True, null=True)


class Proposal(models.Model):
    IDENTIFIER_CHOICES = [
        ('case', 'Case Proposal'),
        ('course', 'Course Proposal'),
    ]
    CATEGORY_CHOICES = [
        ('EG', 'Engineering'),
        ('BC', 'Blockchain'),
        ('FD', 'Finance & Defi'),
        ('WD', 'Web Development'),
        ('DS', 'Data Science & AI'),
        ('UI', 'UI/UX Design'),
        ('CY', 'Cybersecurity'),
        ('OT', 'Other'),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField()
    proposer = models.ForeignKey(User, on_delete=models.CASCADE)
    identifier = models.CharField(max_length=10, choices=IDENTIFIER_CHOICES, default='case')
    created_at = models.DateTimeField(auto_now_add=True)
    category = models.CharField(max_length=3, choices=CATEGORY_CHOICES, default='OT')
    up_votes = models.IntegerField(default=0)
    down_votes = models.IntegerField(default=0)
    expires_at = models.DateTimeField(blank=True, null=True)
    passed = models.BooleanField(default=False)
    score = models.FloatField(default=70.0)
    cover_image = models.ImageField(upload_to='proposal_covers/', blank=True, null=True)

    def save(self, *args, **kwargs):
        # Automatically set expiry based on identifier
        if not self.expires_at:
            if self.identifier == 'course':
                self.expires_at = timezone.now() + timedelta(hours=24)
            elif self.identifier == 'case':
                self.expires_at = timezone.now() + timedelta(hours=48)
        super().save(*args, **kwargs)

    def should_approve(self):
        """Proposal passes if upvotes > downvotes"""
        return self.up_votes >= self.down_votes



    def __str__(self):
        return f"{self.title} ({self.identifier})"


class ProposalEpisode(models.Model):
    proposal = models.ForeignKey(Proposal, on_delete=models.CASCADE, related_name='episodes')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    video = models.FileField(upload_to='proposal_videos/', blank=True, null=True)
    score = models.FloatField(default=70.0)
    transcript = models.TextField(null=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} (Episode of {self.proposal.title})"


class Course(models.Model):
    CATEGORY_CHOICES = [
        ('EG', 'Engineering'),
        ('BC', 'Blockchain'),
        ('FD', 'Finance & Defi'),
        ('WD', 'Web Development'),
        ('DS', 'Data Science & AI'),
        ('UI', 'UI/UX Design'),
        ('CY', 'Cybersecurity'),
        ('OT', 'Other'),
    ]
    title = models.CharField(max_length=200)
    description = models.TextField()
    cover_image = models.ImageField(upload_to='course_covers/', blank=True, null=True)
    creator = models.ForeignKey(User, on_delete=models.CASCADE)
    category = models.CharField(max_length=3, choices=CATEGORY_CHOICES, default='OT')
    score = models.FloatField(default=70.0)
    revenue = models.DecimalField(max_digits=12,decimal_places=2,default=Decimal("0.00"))
    created_at = models.DateTimeField(auto_now_add=True)
    embedding = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.title


class Episode(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='episodes')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    video = models.FileField(upload_to='course_videos/', blank=True, null=True)
    score = models.FloatField(default=70.0)
    transcript = models.TextField(null=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} ({self.course.title})"

class Start_course(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='started_course')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='started_course')
    started_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.student} started {self.course} at {self.started_at}'

class Complete_course(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='completed_course')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='completed_course')
    completed_at = models.DateTimeField(auto_now_add=True)
    certificate_image = models.ImageField(upload_to='certificate/', blank=True, null=True)
    score = models.FloatField(default=0.0)
    tx_hash = models.CharField(max_length=100, null=True)
    token_id = models.IntegerField(null=True)

    def __str__(self):
        return f'{self.student} completed {self.course} at {self.completed_at}'

class EpisodeProgress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    episode = models.ForeignKey(Episode, on_delete=models.CASCADE, related_name='ep_progress')
    progress = models.FloatField(default=0.0)
    last_position = models.FloatField(default=0.0)  # video resume time
    watched_count = models.PositiveIntegerField(default=0)
    completed = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user} has a {self.progress} progress in {self.episode}"


class Vote(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    proposal = models.ForeignKey(Proposal, on_delete=models.CASCADE, related_name='votes')
    vote_type = models.CharField(max_length=10, choices=[('up', 'Upvote'), ('down', 'Downvote')], null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'proposal')

class EmailVerification(models.Model):
    email = models.EmailField(unique=True)
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    def is_expired(self):
        return timezone.now() > self.expires_at

    class Meta:
        indexes = [
            models.Index(fields=['email']),
        ]
class ChatMessage(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20)  # "user" or "assistant"
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

class ConvoSummary(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    content = models.TextField(null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

class Temp_quizscore(models.Model):
    user=models.ForeignKey(User, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    score = models.FloatField(default=0.0)

class Wallet(models.Model):
    user=models.OneToOneField(User, on_delete=models.CASCADE, related_name="wallet")
    wallet=models.CharField(max_length=100)
    p_key = models.CharField(max_length=100)

class Subscribe(models.Model):
    user=models.OneToOneField(User, on_delete=models.CASCADE, related_name="subscribe")
    subscribed_at = models.DateTimeField(auto_now_add=True)
    duration = models.CharField(max_length=20) #monthly or yearly
    is_active =models.BooleanField(default=False)
    active_months = models.IntegerField(default=0)
    expires_at = models.DateTimeField()

class SendSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    asset = models.CharField(max_length=10)
    to_address = models.CharField(max_length=42)
    amount = models.DecimalField(max_digits=20, decimal_places=8)
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)

class ExportSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    otp = models.CharField(max_length=6)
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"ExportSession({self.user})"

class Comments(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    episode = models.ForeignKey(Episode, on_delete=models.CASCADE, related_name='ep_comment', null=True)
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'comment by {self.user}'

class Reply(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    comment = models.ForeignKey(Comments, on_delete=models.CASCADE, related_name='replies')
    reply = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'reply by {self.user} on {self.comment}'

class Searched(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    search = models.CharField(max_length=100)
    searched_at = models.DateTimeField(auto_now_add=True)

class Course_reward(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE,related_name='reward')
    reward_doll = models.DecimalField(max_digits=12,decimal_places=2,default=Decimal("0.00"))
    reward = models.DecimalField(max_digits=12,decimal_places=2,default=Decimal("0.00"))
    sent = models.BooleanField(default=False)
    tx_hash =models.CharField(max_length=100, null=True)
    reward_at =models.DateTimeField(auto_now_add=True)