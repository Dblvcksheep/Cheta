import sys
from time import sleep
from piotechapp.models import Course, Episode,Course_reward,Complete_course,EpisodeProgress,Course_reward
from piotechapp.Blockchain import connect_pkey, send_usdc, check_usdc_balance
from django.utils import timezone
from datetime import timedelta
from django.db.models import Sum
from django.core.management.base import BaseCommand
import os
from dotenv import load_dotenv
from decimal import Decimal

load_dotenv()


reward_pkey = os.environ['REWARD_KEY']
subscribe_pkey = os.environ['SUBSCRIPTION_KEY']
treasury_wallet = os.environ['TREASURY_WALLET']


class Command(BaseCommand):
    help = 'Distribute rewards to eligible course wallets'

    def handle(self, *args, **options):
        acct = connect_pkey(reward_pkey)
        sub_acct = connect_pkey(subscribe_pkey)

        sub_balance = check_usdc_balance(sub_acct, 0)
        sub_balance = sub_balance['balance_usdc']

        reward_percentage = sub_balance*0.3
        treasury_percentage = sub_balance*0.7

        send_usdc(sub_acct,reward_percentage,acct.address)
        send_usdc(sub_acct,treasury_percentage,treasury_wallet)

        sleep(5)

        now = timezone.now()
        start_of_this_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        start_of_last_month = (start_of_this_month - timedelta(days=1)).replace(day=1)

        courses = Course.objects.all()
        Course_reward.objects.all().delete()



        all_course_reward = []
        for course in courses:
            episode = Episode.objects.filter(course=course).all()
            ep_progress = EpisodeProgress.objects.filter(
                course=course,
                updated_at__gte=start_of_last_month,
                updated_at__lt=start_of_this_month
            )

            agg = ep_progress.aggregate(
                watched=Sum('watched_count'),
                progress=Sum('progress')
            )

            watched_count = agg['watched'] or 0
            progress = agg['progress'] or 0



            completed = Complete_course.objects.filter(
                course=course,
                completed_at__gte=start_of_last_month,
                completed_at__lt=start_of_this_month
            ).count()



            completed_85 = Complete_course.objects.filter(
                course=course,
                score__gt=85,
                completed_at__gte=start_of_last_month,
                completed_at__lt=start_of_this_month
            ).count()


            if not episode:
                continue
            N = episode.count()
            episode_weight = 100/N


            total_watched = watched_count * episode_weight
            Active_progress = progress/100 * episode_weight
            WE = total_watched + Active_progress

            relevance_score = course.score/100

            course_reward = ((WE*0.5)+(completed)+(completed_85*1.5))*relevance_score
            course_reward=Decimal(str(course_reward))
            all_course_reward.append(course_reward)

            Course_reward.objects.create(course=course,reward=course_reward)

        total_reward_score = sum(all_course_reward)
        total_reward_score = Decimal(str(total_reward_score))
        balance = check_usdc_balance(acct, 0)
        pool = balance['balance_usdc']
        pool = Decimal(str(pool))

        if total_reward_score == 0:
            print('No reward')
            sys.exit(0)

        course_reward = Course_reward.objects.all()
        for reward in course_reward:
            reward_doll =reward.reward/total_reward_score*pool
            reward_doll = Decimal(str(reward_doll))
            wallet = reward.course.creator.wallet.wallet
            if wallet:

                sleep(5)
                tx=send_usdc(acct, reward_doll, wallet)
                if tx["success"]:
                    reward.tx_hash = tx["tx_hash"]
                    reward.sent = True
                    reward.reward_doll = reward_doll

                    course = reward.course
                    course.revenue += reward_doll

                    reward.save()
                    course.save()
                    self.stdout.write(self.style.SUCCESS(f"✅ Reward sent"))

                else:
                    reward.reward_doll = reward_doll
                    # reward.tx_hash = tx["tx_hash"]
                    print(tx["error"])
                    reward.save()



