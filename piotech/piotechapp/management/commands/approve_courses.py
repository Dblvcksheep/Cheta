import json
from django.core.management.base import BaseCommand
from django.utils import timezone
from piotechapp.models import Proposal, ProposalEpisode, Course, Episode
from sentence_transformers import SentenceTransformer


model = SentenceTransformer('all-MiniLM-L6-v2')

class Command(BaseCommand):
    help = 'Approve or reject expired proposals and convert valid ones into courses'

    def handle(self, *args, **options):
        expired = Proposal.objects.filter(expires_at__lt=timezone.now())

        for prop in expired:
            if prop.identifier == 'course':
                if prop.should_approve():
                    # ✅ Approve course proposal and create course
                    course = Course.objects.create(
                        title=prop.title,
                        description=prop.description,
                        cover_image=prop.cover_image if prop.cover_image else 'default.jpg',
                        creator=prop.proposer,
                        category = prop.category,
                        score = prop.score,
                        embedding = json.dumps(model.encode(prop.title).tolist())
                    )

                    # Copy its episodes
                    for ep in prop.episodes.all():
                        Episode.objects.create(
                            course=course,
                            title=ep.title,
                            description=ep.description,
                            video=ep.video,
                            score = ep.score,
                            transcript = ep.transcript
                        )

                    self.stdout.write(self.style.SUCCESS(f"✅ Approved Course: {prop.title}"))
                else:
                    self.stdout.write(self.style.WARNING(f"❌ Rejected Course: {prop.title}"))

            elif prop.identifier == 'case':
                if prop.should_approve():
                    self.stdout.write(self.style.SUCCESS(f"✅ Approved Case: {prop.title}"))
                else:
                    self.stdout.write(self.style.WARNING(f"❌ Rejected Case: {prop.title}"))

            # Delete after processing
            prop.delete()