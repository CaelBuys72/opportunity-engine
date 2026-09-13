"""Inferred candidate problems for Build 2 test audiences (Mode B).

These are `basis:"inferred"` — plausible problems derived from audience context,
NOT observed evidence. They carry no sources, no frequency, no demand claims.
The engine stores them as inferred/LOW and never as observed.
Keyed by audience_id. Replaceable later by real retrieval.
"""

SEED = {
 # ---------- Airbnb hosts with 1-5 properties ----------
 "aud-travel-and-hospitality-short-term-rentals-airbnb-hosts-with-1-5-properties": [
  {"statement": "Hosts struggle to price weekends and weekdays differently.", "normalized_problem": "weekend vs weekday pricing uncertainty", "problem_type": "financial_problem", "desired_outcome": "Set confident day-of-week nightly rates."},
  {"statement": "Hosts don't know when to raise prices for local events.", "normalized_problem": "event-based pricing uncertainty", "problem_type": "financial_problem", "desired_outcome": "Adjust rates for local demand spikes."},
  {"statement": "Hosts have empty nights / gaps between bookings.", "normalized_problem": "occupancy gaps between bookings", "problem_type": "performance_problem", "desired_outcome": "Reduce vacant nights."},
  {"statement": "Guest messaging is inconsistent and time-consuming.", "normalized_problem": "inconsistent guest messaging", "problem_type": "communication_problem", "desired_outcome": "Send consistent, timely guest messages."},
  {"statement": "Coordinating cleaners around checkouts is hard.", "normalized_problem": "cleaner turnover coordination", "problem_type": "workflow_problem", "desired_outcome": "Reliably schedule turnovers."},
  {"statement": "New hosts don't know what to put in a welcome book / house manual.", "normalized_problem": "welcome book contents unclear", "problem_type": "knowledge_gap", "desired_outcome": "Produce a complete house manual."},
  {"statement": "Managing a listing remotely from another city is stressful.", "normalized_problem": "remote listing management", "problem_type": "operational_problem", "desired_outcome": "Run the property hands-off."},
  {"statement": "Hosts are unsure how to set minimum-stay rules.", "normalized_problem": "minimum-stay rule confusion", "problem_type": "decision_problem", "desired_outcome": "Choose the right min-stay settings."},
  {"statement": "Handling difficult or rule-breaking guests is draining.", "normalized_problem": "difficult guest handling", "problem_type": "emotional_friction", "desired_outcome": "Handle problem guests calmly and safely."},
  {"statement": "Keeping reviews consistently high is hard.", "normalized_problem": "maintaining consistent reviews", "problem_type": "retention_problem", "desired_outcome": "Sustain 5-star reviews."},
  {"statement": "Tracking expenses and profit per property is messy.", "normalized_problem": "per-property expense tracking", "problem_type": "financial_problem", "desired_outcome": "See true profit per listing."},
  {"statement": "Writing a listing that ranks and converts is confusing.", "normalized_problem": "listing optimization uncertainty", "problem_type": "performance_problem", "desired_outcome": "Improve listing visibility and bookings."},
  {"statement": "Restocking supplies and consumables is easy to forget.", "normalized_problem": "supply restocking tracking", "problem_type": "operational_problem", "desired_outcome": "Never run out of guest supplies."},
  {"statement": "Setting up automated/dynamic pricing tools is intimidating.", "normalized_problem": "dynamic pricing tool setup", "problem_type": "technical_problem", "desired_outcome": "Automate pricing confidently."},
 ],
 # ---------- Independent nail technicians ----------
 "aud-beauty-and-personal-care-nail-services-independent-nail-technicians": [
  {"statement": "Techs don't know what to charge to stay profitable.", "normalized_problem": "service pricing uncertainty", "problem_type": "financial_problem", "desired_outcome": "Price services for real profit."},
  {"statement": "Techs are scared to raise their prices.", "normalized_problem": "fear of raising prices", "problem_type": "emotional_friction", "desired_outcome": "Raise rates without losing clients."},
  {"statement": "Clients keep negotiating or asking for discounts.", "normalized_problem": "client price negotiation", "problem_type": "communication_problem", "desired_outcome": "Hold firm, fair pricing."},
  {"statement": "Techs don't know their true product cost per set.", "normalized_problem": "product cost per service unknown", "problem_type": "financial_problem", "desired_outcome": "Know cost of goods per service."},
  {"statement": "No-shows and last-minute cancellations lose income.", "normalized_problem": "no-shows and cancellations", "problem_type": "operational_problem", "desired_outcome": "Reduce no-shows with policies/deposits."},
  {"statement": "Filling the appointment book consistently is hard.", "normalized_problem": "inconsistent bookings", "problem_type": "acquisition_problem", "desired_outcome": "Keep the calendar full."},
  {"statement": "Marketing on Instagram feels confusing and inconsistent.", "normalized_problem": "inconsistent social marketing", "problem_type": "acquisition_problem", "desired_outcome": "Market consistently on social."},
  {"statement": "Getting clients to rebook regularly is difficult.", "normalized_problem": "client rebooking / retention", "problem_type": "retention_problem", "desired_outcome": "Turn one-offs into regulars."},
  {"statement": "Managing intake and consent forms is disorganized.", "normalized_problem": "client intake/consent disorganization", "problem_type": "workflow_problem", "desired_outcome": "Streamline intake and consent."},
  {"statement": "Setting deposit and cancellation policies is unclear.", "normalized_problem": "deposit/cancellation policy unclear", "problem_type": "decision_problem", "desired_outcome": "Set clear booking policies."},
  {"statement": "Tracking income and expenses for taxes is stressful.", "normalized_problem": "income/expense tracking for tax", "problem_type": "financial_problem", "desired_outcome": "Stay tax-ready year round."},
  {"statement": "Building a first client base from scratch is slow.", "normalized_problem": "building initial clientele", "problem_type": "acquisition_problem", "desired_outcome": "Grow a starting client book."},
  {"statement": "Deciding which services to offer and package is unclear.", "normalized_problem": "service menu decisions", "problem_type": "decision_problem", "desired_outcome": "Design a profitable service menu."},
 ],
 # ---------- Freelancers with inconsistent income ----------
 "aud-freelancing-and-solopreneurship-freelance-operations-and-admin-freelancers-with-inconsistent-irregular-income": [
  {"statement": "Income varies month to month, making budgeting hard.", "normalized_problem": "budgeting on variable income", "problem_type": "financial_problem", "desired_outcome": "Budget reliably despite variable income."},
  {"statement": "Freelancers don't know what's safe to pay themselves.", "normalized_problem": "owner pay / draw uncertainty", "problem_type": "financial_problem", "desired_outcome": "Pay themselves a stable amount."},
  {"statement": "Feast-or-famine client cycles cause stress.", "normalized_problem": "feast-or-famine pipeline", "problem_type": "acquisition_problem", "desired_outcome": "Smooth out the client pipeline."},
  {"statement": "Setting money aside for taxes is inconsistent.", "normalized_problem": "irregular tax set-aside", "problem_type": "compliance_problem", "desired_outcome": "Set aside the right amount each payment."},
  {"statement": "Chasing late invoices hurts cashflow.", "normalized_problem": "late invoice cashflow gaps", "problem_type": "financial_problem", "desired_outcome": "Get paid on time."},
  {"statement": "No emergency buffer for slow months.", "normalized_problem": "no buffer for slow months", "problem_type": "financial_problem", "desired_outcome": "Build a slow-month buffer."},
  {"statement": "Hard to forecast next quarter's income.", "normalized_problem": "income forecasting difficulty", "problem_type": "planning_problem", "desired_outcome": "Forecast income with some confidence."},
  {"statement": "Deciding whether to take low-paying work in slow months.", "normalized_problem": "low-pay work decisions in slow periods", "problem_type": "decision_problem", "desired_outcome": "Decide which work to accept."},
  {"statement": "Separating business and personal money is messy.", "normalized_problem": "business/personal money mixing", "problem_type": "workflow_problem", "desired_outcome": "Cleanly separate finances."},
  {"statement": "Anxiety about money makes planning avoidance worse.", "normalized_problem": "money anxiety and avoidance", "problem_type": "emotional_friction", "desired_outcome": "Reduce money stress with a system."},
  {"statement": "Pricing to cover irregular income is guesswork.", "normalized_problem": "pricing for income stability", "problem_type": "financial_problem", "desired_outcome": "Price to stabilize take-home."},
  {"statement": "Tracking which clients/projects are actually profitable.", "normalized_problem": "per-client profitability tracking", "problem_type": "financial_problem", "desired_outcome": "Know which work pays best."},
 ],
 # ---------- Short-form creators trying to post consistently ----------
 "aud-content-creation-and-creator-economy-short-form-video-creators-trying-to-post-consistently-on-reels-tiktok": [
  {"statement": "Creators keep running out of content ideas.", "normalized_problem": "running out of ideas", "problem_type": "knowledge_gap", "desired_outcome": "Always have a backlog of ideas."},
  {"statement": "Posting consistently is hard to sustain.", "normalized_problem": "posting consistency", "problem_type": "planning_problem", "desired_outcome": "Maintain a steady posting cadence."},
  {"statement": "Batching and scheduling content is disorganized.", "normalized_problem": "content batching/scheduling", "problem_type": "workflow_problem", "desired_outcome": "Batch and schedule reliably."},
  {"statement": "Hooks that stop the scroll are hard to write.", "normalized_problem": "writing strong hooks", "problem_type": "performance_problem", "desired_outcome": "Write scroll-stopping hooks."},
  {"statement": "Editing takes too long per video.", "normalized_problem": "slow editing workflow", "problem_type": "time_problem", "desired_outcome": "Edit faster with a repeatable process."},
  {"statement": "Low or flat view counts are discouraging.", "normalized_problem": "low/flat views", "problem_type": "performance_problem", "desired_outcome": "Improve reach and views."},
  {"statement": "Repurposing one video across platforms is manual.", "normalized_problem": "cross-platform repurposing", "problem_type": "workflow_problem", "desired_outcome": "Repurpose content efficiently."},
  {"statement": "Burnout from the pressure to always post.", "normalized_problem": "creator burnout", "problem_type": "emotional_friction", "desired_outcome": "Sustain output without burnout."},
  {"statement": "Deciding what niche/content pillars to commit to.", "normalized_problem": "niche/pillar decisions", "problem_type": "decision_problem", "desired_outcome": "Commit to clear content pillars."},
  {"statement": "Understanding analytics to know what's working.", "normalized_problem": "interpreting analytics", "problem_type": "knowledge_gap", "desired_outcome": "Read analytics and act on them."},
  {"statement": "Turning views into followers/email subscribers.", "normalized_problem": "converting views to audience", "problem_type": "acquisition_problem", "desired_outcome": "Convert viewers into a real audience."},
  {"statement": "Planning a week of content in advance.", "normalized_problem": "weekly content planning", "problem_type": "planning_problem", "desired_outcome": "Plan a week of content quickly."},
 ],
 # ---------- New puppy owners in the first weeks ----------
 "aud-pets-and-animal-care-dog-training-new-puppy-owners-in-the-first-weeks": [
  {"statement": "Owners feel overwhelmed in the first days with a puppy.", "normalized_problem": "first-week overwhelm", "problem_type": "emotional_friction", "desired_outcome": "Feel in control of the first weeks."},
  {"statement": "Potty training is confusing and inconsistent.", "normalized_problem": "potty training confusion", "problem_type": "knowledge_gap", "desired_outcome": "Follow a reliable potty routine."},
  {"statement": "Crate training feels cruel or isn't working.", "normalized_problem": "crate training difficulty", "problem_type": "knowledge_gap", "desired_outcome": "Crate train calmly and effectively."},
  {"statement": "Puppy cries all night / disrupted sleep.", "normalized_problem": "nighttime crying/sleep", "problem_type": "operational_problem", "desired_outcome": "Get the puppy sleeping through."},
  {"statement": "Owners don't have a daily schedule for the puppy.", "normalized_problem": "no daily puppy schedule", "problem_type": "planning_problem", "desired_outcome": "Follow a clear daily schedule."},
  {"statement": "Biting and nipping is hard to curb.", "normalized_problem": "biting/nipping", "problem_type": "knowledge_gap", "desired_outcome": "Reduce biting with a method."},
  {"statement": "Unsure which commands to teach first and how.", "normalized_problem": "which commands first", "problem_type": "decision_problem", "desired_outcome": "Know the command order to teach."},
  {"statement": "Socialization window feels confusing and time-pressured.", "normalized_problem": "socialization uncertainty", "problem_type": "time_problem", "desired_outcome": "Socialize the puppy on time."},
  {"statement": "Leash walking is chaotic.", "normalized_problem": "leash walking difficulty", "problem_type": "knowledge_gap", "desired_outcome": "Walk calmly on a leash."},
  {"statement": "Conflicting advice online makes decisions hard.", "normalized_problem": "conflicting training advice", "problem_type": "decision_problem", "desired_outcome": "Follow one trustworthy plan."},
  {"statement": "Tracking vaccinations and vet milestones.", "normalized_problem": "vaccination/vet tracking", "problem_type": "operational_problem", "desired_outcome": "Stay on top of vet milestones."},
  {"statement": "Separation anxiety when left alone.", "normalized_problem": "separation anxiety", "problem_type": "emotional_friction", "desired_outcome": "Build alone-time tolerance."},
 ],
}
