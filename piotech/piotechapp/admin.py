from django.contrib import admin
from .models import EmailVerification,Proposal,ProposalEpisode,Course,Episode, Start_course,Complete_course, EpisodeProgress,Vote,UserProfile, Wallet, ChatMessage, ConvoSummary,Temp_quizscore,Subscribe

# Register your models here.
admin.site.register(EmailVerification)
admin.site.register(Proposal)
admin.site.register(ProposalEpisode)
admin.site.register(Course)
admin.site.register(Episode)
admin.site.register(EpisodeProgress)
admin.site.register(Start_course)
admin.site.register(Complete_course)
admin.site.register(Vote)
admin.site.register(Wallet)
admin.site.register(ConvoSummary)
admin.site.register(ChatMessage)
admin.site.register(Temp_quizscore)
admin.site.register(Subscribe)