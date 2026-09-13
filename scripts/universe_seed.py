"""Seed taxonomy for the Market Universe (Build 1).

Hand-authored, commercially-oriented. Audiences are segmented by role / stage /
business model / constraint / experience — NOT synonyms of their submarket.
This is `basis: "inferred"` taxonomy; it asserts NO demand/size/creator data.

Shape: { market_name: { "description": str, "submarkets": { submarket_name: [audience, ...] } } }
Future: replace this dict with AI generation, curated files, or datasets — the
generator in build_universe.py consumes this shape only.
"""

_BASE = {
  "Freelancing & Solopreneurship": {
    "description": "People running a business of one, selling their skills directly to clients.",
    "submarkets": {
      "Freelance Operations & Admin": [
        "Freelancers in their first year", "Freelancers with inconsistent / irregular income",
        "Freelancers juggling many simultaneous clients"],
      "Freelance Pricing & Sales": [
        "Freelancers who undercharge and want to raise rates",
        "Freelancers writing their first proposals and contracts",
        "Freelancers moving from hourly to value/retainer pricing"],
      "Freelance Taxes & Money": [
        "US 1099 freelancers handling quarterly estimated taxes",
        "Freelancers setting money aside for taxes for the first time",
        "Freelancers tracking deductible business expenses"],
      "Finding Freelance Clients": [
        "New freelancers with no portfolio yet",
        "Freelancers over-reliant on one platform (Upwork/Fiverr)",
        "Freelancers transitioning from employment to full-time freelance"],
      "Freelance Service Delivery": [
        "Freelancers formalizing client onboarding",
        "Freelancers dealing with scope creep",
        "Freelancers productizing a repeatable service"],
    }},
  "Small Business & Entrepreneurship": {
    "description": "Owner-operators and founders of small, often local, businesses.",
    "submarkets": {
      "Bookkeeping & Business Finance": [
        "First-time small-business owners doing their own books",
        "Cash-based service businesses tracking true profit",
        "Owners preparing for their first business tax season"],
      "Local Service Businesses": [
        "Owner-operators in the trades (plumbers, electricians)",
        "Local businesses trying to generate more inbound calls",
        "Service businesses managing quotes and scheduling"],
      "Hiring & Team": [
        "Owners making their very first hire",
        "Small teams documenting SOPs",
        "Businesses onboarding contractors"],
      "Business Launch": [
        "People validating a business idea before launch",
        "Side-hustlers going full-time",
        "People registering and structuring a new business"],
      "Local Marketing": [
        "Businesses managing their Google Business Profile",
        "Service businesses collecting and using reviews",
        "Owners running their first paid ads"],
    }},
  "Personal Finance": {
    "description": "Individuals managing money, debt, saving, and investing.",
    "submarkets": {
      "Budgeting & Cashflow": [
        "People building their first real budget",
        "Households with irregular / variable income",
        "Couples merging their finances"],
      "Debt Payoff": [
        "People starting a structured debt-payoff plan",
        "People juggling multiple credit cards",
        "Recent graduates managing student loans"],
      "Saving & Sinking Funds": [
        "People building an emergency fund from zero",
        "Savers planning for a specific large purchase",
        "People automating their savings"],
      "Investing Basics": [
        "First-time retail investors",
        "People setting up retirement accounts",
        "DIY index investors"],
      "Financial Organization": [
        "People organizing bills and subscriptions",
        "People tracking their net worth",
        "People assembling financial documents for tax time"],
    }},
  "Career & Job Search": {
    "description": "Professionals finding jobs and advancing careers.",
    "submarkets": {
      "Resumes & Applications": [
        "Job seekers getting screened out by ATS",
        "Career changers with no direct experience",
        "New graduates writing a first resume"],
      "Interviewing": [
        "People preparing for behavioral interviews",
        "Candidates negotiating a job offer",
        "Technical candidates prepping take-home assignments"],
      "Career Growth": [
        "Individual contributors seeking a first promotion",
        "New managers in their first 90 days",
        "Professionals building a personal brand"],
      "Networking": [
        "Introverts building a professional network",
        "People running informational interviews",
        "Job seekers using LinkedIn strategically"],
      "Career Transitions": [
        "People returning to work after a career gap",
        "Military members transitioning to civilian roles",
        "People moving from corporate employment to self-employment"],
    }},
  "E-commerce & Online Selling": {
    "description": "People selling physical or print products online.",
    "submarkets": {
      "Etsy & Handmade": [
        "New Etsy sellers with no sales yet",
        "Handmade sellers pricing their products",
        "Etsy sellers improving listing SEO"],
      "Print-on-Demand": [
        "Beginners launching a POD store",
        "POD sellers researching niches",
        "POD sellers designing higher-converting products"],
      "Amazon Selling": [
        "New Amazon FBA sellers",
        "Private-label sellers sourcing products",
        "Sellers managing Amazon PPC ads"],
      "Shopify DTC": [
        "Founders launching a first Shopify store",
        "Store owners improving conversion rate",
        "DTC brands increasing repeat purchases"],
      "Reselling & Flipping": [
        "Thrift and vintage resellers",
        "Sneaker and collectible flippers",
        "People sourcing inventory to resell"],
    }},
  "Content Creation & Creator Economy": {
    "description": "Independent creators building audiences and monetizing them.",
    "submarkets": {
      "Short-Form Video": [
        "Creators trying to post consistently on Reels/TikTok",
        "Creators who keep running out of content ideas",
        "Operators of faceless / niche channels"],
      "YouTube": [
        "New YouTubers before monetization",
        "Creators scripting long-form videos",
        "Channels improving thumbnails and click-through"],
      "Newsletters": [
        "Writers launching a first newsletter",
        "Operators growing newsletter subscribers",
        "Writers monetizing an email list"],
      "Podcasting": [
        "First-time podcasters",
        "Podcasters growing their downloads",
        "Podcasters landing their first sponsors"],
      "Creator Monetization": [
        "Creators launching a first digital product",
        "Creators setting brand-deal rates",
        "Creators building a membership or community"],
    }},
  "Real Estate & Property": {
    "description": "Buying, investing in, renting out, and selling property.",
    "submarkets": {
      "Buying a Home": [
        "First-time home buyers",
        "Buyers navigating mortgage pre-approval",
        "Buyers budgeting closing and moving costs"],
      "Property Investing": [
        "First-time rental-property investors",
        "House hackers",
        "Value-add / BRRRR investors"],
      "Landlording": [
        "Small landlords self-managing tenants",
        "Landlords screening applicants",
        "Landlords handling maintenance and turnover"],
      "Selling a Home": [
        "For-sale-by-owner sellers",
        "Sellers staging on a budget",
        "Sellers timing their sale"],
      "Real Estate Agents": [
        "New agents building a pipeline",
        "Agents managing their social media presence",
        "Agents systematizing client follow-up"],
    }},
  "Travel & Hospitality": {
    "description": "Travel planning and running short-term rental / hospitality operations.",
    "submarkets": {
      "Short-Term Rentals": [
        "New Airbnb hosts in their first year",
        "Airbnb hosts with 1-5 properties",
        "Remote hosts managing properties from another city"],
      "STR Operations": [
        "Hosts systematizing cleaning and turnover",
        "Hosts writing guest communication and manuals",
        "Hosts automating listings and dynamic pricing"],
      "Travel Planning": [
        "First-time solo travelers",
        "Points and miles optimizers",
        "Families planning trips on a budget"],
      "Digital Nomad Travel": [
        "People going remote / nomad for the first time",
        "Nomads managing visas and logistics",
        "Nomads working across time zones"],
      "Hospitality Businesses": [
        "Small B&B / guesthouse owners",
        "Tour and experience operators",
        "Hosts scaling to a co-host / property-management model"],
    }},
  "Beauty & Personal Care": {
    "description": "Independent beauty-service professionals and their businesses.",
    "submarkets": {
      "Nail Services": [
        "Independent nail technicians",
        "Beginner nail techs building a client book",
        "Mobile nail technicians"],
      "Lash & Brow Services": [
        "Lash artists setting profitable prices",
        "New lash techs building clientele",
        "Brow artists adding new services"],
      "Hair Professionals": [
        "Booth-renting hairstylists",
        "Salon owners managing staff",
        "Stylists building a personal brand"],
      "Skincare & Esthetics": [
        "Solo estheticians",
        "Estheticians handling client intake and consults",
        "Estheticians retailing take-home products"],
      "Beauty Business Admin": [
        "Beauty pros setting no-show / deposit policies",
        "Beauty pros marketing on Instagram",
        "Beauty pros managing their booking flow"],
    }},
  "Fitness & Physical Training": {
    "description": "Training people and coaching physical performance.",
    "submarkets": {
      "Personal Training": [
        "Independent personal trainers managing clients",
        "Trainers moving clients online",
        "Trainers programming for many clients at once"],
      "Online Coaching": [
        "Coaches running check-ins and accountability",
        "Coaches building reusable program templates",
        "Coaches trying to retain clients longer"],
      "Strength & Physique": [
        "Beginners attempting body recomposition",
        "Lifters planning a cut or bulk",
        "People tracking macros for the first time"],
      "Running & Endurance": [
        "First-time race trainees",
        "Runners following a structured plan",
        "Runners trying to avoid injury"],
      "Home & Bodyweight Fitness": [
        "People training at home with minimal equipment",
        "Busy parents fitting in short workouts",
        "Beginners building a first routine"],
    }},
  "Health & Wellness": {
    "description": "Everyday health, sleep, nutrition, and behavior change.",
    "submarkets": {
      "Sleep": [
        "Adults with disrupted sleep",
        "Shift workers managing sleep",
        "People building a wind-down routine"],
      "Nutrition & Meal Planning": [
        "People meal-prepping for the week",
        "Families planning budget-friendly meals",
        "People eating for a specific diet (keto, vegan)"],
      "Mental Health & Stress": [
        "People building stress-management habits",
        "People managing day-to-day anxiety",
        "People starting journaling or mindfulness"],
      "Habit & Behavior Change": [
        "People building a consistent morning routine",
        "People trying to break a specific bad habit",
        "People who want to track habits simply"],
      "Chronic Condition Management": [
        "People newly managing a chronic condition",
        "Caregivers tracking a family member's care",
        "People organizing their medical information"],
    }},
  "Parenting & Family": {
    "description": "Raising children and running family logistics.",
    "submarkets": {
      "Newborn & Infant Care": [
        "Sleep-deprived parents of 0-18 month infants",
        "First-time parents preparing for a newborn",
        "Parents navigating sleep regressions"],
      "Toddler & Early Childhood": [
        "Parents managing toddler behavior",
        "Parents potty-training",
        "Parents building early daily routines"],
      "School-Age Parenting": [
        "Parents supporting homework and study",
        "Parents managing kids' screen time",
        "Parents handling extracurricular logistics"],
      "Family Organization": [
        "Parents coordinating a shared family calendar",
        "Parents meal-planning for picky eaters",
        "Parents dividing chores and responsibilities"],
      "Special & Additional Needs": [
        "Parents of newly-diagnosed children",
        "Parents navigating IEPs and school support",
        "Caregivers coordinating multiple therapies"],
    }},
  "Relationships & Dating": {
    "description": "Dating, couples, and major relationship milestones.",
    "submarkets": {
      "Online Dating": [
        "People optimizing dating-app profiles",
        "People navigating first messages",
        "People re-entering dating after a breakup"],
      "Couples & Communication": [
        "Couples improving communication",
        "Couples coordinating finances and logistics",
        "Long-distance couples"],
      "Wedding Planning": [
        "Couples DIY-planning a wedding on a budget",
        "People writing wedding speeches",
        "Couples managing guest lists and vendors"],
      "Marriage & Long-Term": [
        "Newlyweds adjusting to married life",
        "Parents maintaining connection with young kids",
        "Couples planning shared long-term goals"],
      "Breakups & Solo": [
        "People recovering from a breakup",
        "People rebuilding social life after divorce",
        "People intentionally choosing to be single"],
    }},
  "Education & Tutoring": {
    "description": "Teaching, tutoring, test prep, and skill courses.",
    "submarkets": {
      "Test Prep": [
        "Students preparing for standardized tests",
        "Adults retaking a certification exam",
        "Parents supporting a child's test prep"],
      "Tutoring Businesses": [
        "Independent tutors finding students",
        "Tutors moving lessons online",
        "Tutors packaging lessons into courses"],
      "Language Learning": [
        "Self-learners stuck at the intermediate plateau (B1)",
        "People preparing for a language proficiency exam",
        "People trying to build a daily practice habit"],
      "Teachers & Educators": [
        "K-12 teachers reducing lesson-planning time",
        "Teachers creating classroom resources",
        "Teachers managing grading and admin"],
      "Skill Courses": [
        "People creating and selling a first online course",
        "Course creators structuring their curriculum",
        "Instructors improving course completion rates"],
    }},
  "Home & DIY": {
    "description": "Organizing, renovating, gardening, and maintaining a home.",
    "submarkets": {
      "Home Organization & Decluttering": [
        "Overwhelmed adults starting to declutter",
        "People maintaining an already-organized home",
        "People organizing a specific room (kitchen, garage)"],
      "Home Renovation": [
        "First-time renovators budgeting a project",
        "DIYers doing their own repairs",
        "Homeowners hiring and managing contractors"],
      "Gardening": [
        "Beginner vegetable gardeners",
        "Gardeners planning by climate zone and season",
        "Small-space / container gardeners"],
      "Interior Styling": [
        "People decorating a first apartment on a budget",
        "Renters styling without renovating",
        "People planning a single-room redesign"],
      "Home Maintenance": [
        "New homeowners learning basic upkeep",
        "People building a home-maintenance schedule",
        "People handling seasonal / winter prep"],
    }},
  "Pets & Animal Care": {
    "description": "Caring for pets and running pet-service businesses.",
    "submarkets": {
      "Dog Training": [
        "New puppy owners in the first weeks",
        "Owners fixing a specific behavior (leash, barking)",
        "Owners crate and potty training"],
      "Pet Health & Nutrition": [
        "Owners planning their pet's diet",
        "Owners managing a pet's health condition",
        "Owners budgeting for pet care"],
      "Pet Businesses": [
        "Dog walkers and sitters starting out",
        "Groomers building clientele",
        "Pet-service pros scheduling clients"],
      "Cats & Small Pets": [
        "First-time cat owners",
        "Owners solving litter or behavior issues",
        "Multi-cat households"],
      "Specialty & Exotic": [
        "New reptile and aquarium keepers",
        "Owners setting up a habitat",
        "Hobbyists maintaining tanks and enclosures"],
    }},
  "Hobbies & Creative Skills": {
    "description": "Skill-based hobbies people learn, practice, and sometimes sell.",
    "submarkets": {
      "Fiber & Crafts": [
        "Beginner crocheters finishing a first project",
        "Knitters following written patterns",
        "Crafters selling handmade goods"],
      "Baking & Home Cooking": [
        "Beginner sourdough bakers troubleshooting loaves",
        "Home cooks meal-planning weekly",
        "People baking for gifts and events"],
      "Music": [
        "Adult beginners learning an instrument",
        "Self-taught musicians past a plateau",
        "Hobbyists recording music at home"],
      "Art & Illustration": [
        "Beginner digital artists",
        "Artists building a portfolio",
        "Hobbyists selling prints and commissions"],
      "Tabletop & Games": [
        "New D&D game masters prepping sessions",
        "Game masters trying to reduce prep time",
        "Players running a first campaign"],
    }},
  "Productivity & Self-Organization": {
    "description": "Systems for managing tasks, knowledge, goals, and focus.",
    "submarkets": {
      "Task & Time Management": [
        "People building a reliable task system",
        "People overwhelmed by their to-do list",
        "People time-blocking their week"],
      "Note-Taking & Knowledge": [
        "People building a second-brain / notes system",
        "Students organizing study notes",
        "Researchers managing references"],
      "Goal & Habit Systems": [
        "People planning quarterly and annual goals",
        "People trying to track progress consistently",
        "People running weekly reviews"],
      "ADHD & Executive Function": [
        "Adults with ADHD who abandon planners",
        "People needing simple, sustainable systems",
        "People managing focus and distraction"],
      "Digital Organization": [
        "People organizing files and photos",
        "People taming an overflowing email inbox",
        "People managing passwords and accounts"],
    }},
  "Technology & Software": {
    "description": "Learning to build software and running small tech operations.",
    "submarkets": {
      "Learning to Code": [
        "Self-taught beginners choosing a path",
        "Bootcamp grads building a portfolio",
        "Career switchers moving into tech"],
      "Indie Hacking & SaaS": [
        "Solo devs launching a first product",
        "Indie hackers searching for an idea",
        "Makers trying to get their first users"],
      "Data & Analytics": [
        "People learning SQL and analytics",
        "Analysts building dashboards",
        "People automating recurring reports"],
      "IT & Support": [
        "Small-business owners self-managing IT",
        "People setting up home networks / servers",
        "Aspiring IT-certification candidates"],
      "No-Code & Automation": [
        "Non-technical founders building with no-code",
        "People automating manual workflows",
        "People connecting their tools and APIs"],
    }},
  "Food & Culinary": {
    "description": "Home cooking systems, specialty diets, and small food businesses.",
    "submarkets": {
      "Home Meal Systems": [
        "Busy people reducing 'what's for dinner' decisions",
        "People batch-cooking for the week",
        "People cooking around dietary restrictions"],
      "Specialty Diets": [
        "People starting a specific diet",
        "People with allergies or intolerances planning meals",
        "People meal-planning for a health goal"],
      "Food Businesses": [
        "Home-based food and bakery sellers",
        "Cottage-food entrepreneurs pricing products",
        "Food creators building a brand"],
      "Beverages & Fermentation": [
        "Home coffee enthusiasts dialing in their setup",
        "Home brewers and fermenters",
        "People making non-alcoholic craft drinks"],
      "Meal Prep for Fitness": [
        "People prepping macro-based meals",
        "Athletes fueling their training",
        "People cooking high-protein on a budget"],
    }},
}


# ==========================================================================
# UNIVERSE EXPANSION V1  (added 2026-09) — deepen existing markets + 10 new.
# Existing _BASE entries are left untouched so their deterministic IDs (and the
# downstream problems/opportunities attached to them) stay stable. New submarket
# names never collide with existing ones. basis stays "inferred" (taxonomy only).
# ==========================================================================

# ---- additional submarkets for the existing 20 markets (deepening) ----
_EXPANSION_SUBMARKETS = {
  "Freelancing & Solopreneurship": {
    "Freelance Positioning & Niching": [
      "Generalist freelancers trying to differentiate",
      "Freelancers choosing a profitable niche",
      "Freelancers writing a clear, specific offer"],
    "Freelance Systems & Tools": [
      "Freelancers building a client-management dashboard",
      "Freelancers automating repetitive admin",
      "Freelancers assembling their software stack"],
    "Scaling Beyond Solo": [
      "Freelancers subcontracting overflow work",
      "Freelancers turning a service into a small studio",
      "Freelancers raising rates to reduce workload"],
  },
  "Small Business & Entrepreneurship": {
    "Operations & SOPs": [
      "Owners documenting core processes",
      "Owners reducing owner-dependence in daily ops",
      "Teams standardizing service delivery"],
    "Customer Retention & Loyalty": [
      "Businesses building repeat-customer habits",
      "Owners launching a referral or loyalty program",
      "Businesses winning back lapsed customers"],
    "Growth & Strategy": [
      "Owners stuck at a revenue plateau",
      "Owners planning a considered expansion",
      "Owners choosing which numbers to track"],
  },
  "Personal Finance": {
    "Credit & Score": [
      "People rebuilding a damaged credit score",
      "First-time credit-card users avoiding traps",
      "People disputing credit-report errors"],
    "Personal Taxes": [
      "W-2 employees trying to maximize their refund",
      "People with side-income filing taxes for the first time",
      "People organizing documents before tax season"],
    "Financial Independence & Retirement": [
      "People pursuing FIRE (financial independence)",
      "Mid-career people planning for retirement",
      "People calculating their 'enough' number"],
  },
  "Career & Job Search": {
    "Salary & Compensation": [
      "People benchmarking their market salary",
      "Employees negotiating a raise or promotion",
      "People evaluating equity and total comp"],
    "Remote & Flexible Work": [
      "People searching specifically for remote jobs",
      "People building a productive remote setup",
      "People weighing contract vs full-time roles"],
  },
  "E-commerce & Online Selling": {
    "Email & Retention Marketing": [
      "Store owners setting up their first email flows",
      "Brands recovering abandoned carts",
      "DTC owners increasing customer lifetime value"],
    "Subscription & Membership Commerce": [
      "Brands launching a subscription box",
      "Stores adding a membership tier",
      "Subscription brands reducing churn"],
  },
  "Content Creation & Creator Economy": {
    "Audience Growth & Distribution": [
      "Creators repurposing content across platforms",
      "Creators stuck at a follower plateau",
      "Creators using search/SEO for discovery"],
    "Personal Brand & Authority": [
      "Creators building a personal brand from scratch",
      "Experts turning knowledge into content",
      "Founders growing an audience on LinkedIn/X"],
  },
  "Real Estate & Property": {
    "Real Estate Financing & Deals": [
      "Investors analyzing whether a deal works",
      "Buyers using creative financing",
      "First-time commercial-property buyers"],
    "Mortgage & Refinance": [
      "Homeowners deciding whether to refinance",
      "Buyers comparing mortgage options",
      "Owners planning to pay off a mortgage early"],
  },
  "Travel & Hospitality": {
    "Group & Event Travel": [
      "People organizing a group trip",
      "Couples planning a destination wedding",
      "People coordinating a family reunion"],
    "Travel Logistics & Prep": [
      "People packing and organizing for long trips",
      "People handling visas, insurance, and docs",
      "Frequent business travelers optimizing routine"],
  },
  "Beauty & Personal Care": {
    "Makeup Artistry": [
      "Freelance makeup artists building a kit",
      "Bridal makeup artists booking weddings",
      "MUAs finding and retaining clients"],
    "Beauty Content & Education": [
      "Beauty pros teaching technique online",
      "Beauty pros selling courses and guides",
      "Beauty pros growing on Instagram/TikTok"],
  },
  "Fitness & Physical Training": {
    "Group Fitness & Studios": [
      "Studio owners filling their classes",
      "Group instructors building a following",
      "Boutique-gym operators managing retention"],
    "Specialty Populations": [
      "Trainers for pre/postnatal clients",
      "Trainers working with older adults",
      "Coaches handling return-to-training after injury"],
  },
  "Health & Wellness": {
    "Women's Health": [
      "People tracking their cycle and symptoms",
      "People navigating perimenopause / menopause",
      "People managing postpartum recovery"],
    "Longevity & Energy": [
      "People trying to fix low daily energy",
      "People acting on wearable / lab data",
      "People building a supplement routine"],
  },
  "Parenting & Family": {
    "Teen Parenting": [
      "Parents navigating teen independence",
      "Parents managing teen phone and social media",
      "Parents guiding college and career choices"],
    "Parenting Finances & Planning": [
      "Parents budgeting for a new baby",
      "Parents saving for their kids' education",
      "Parents coordinating childcare logistics"],
  },
  "Relationships & Dating": {
    "Friendship & Social Life": [
      "Adults trying to make friends as grown-ups",
      "People rebuilding a social circle after a move",
      "People improving everyday social confidence"],
  },
  "Education & Tutoring": {
    "Homeschooling": [
      "New homeschool parents choosing a curriculum",
      "Homeschoolers planning the school year",
      "Parents tracking homeschool progress"],
    "Cohort & Community Learning": [
      "Creators running a cohort-based course",
      "Operators building a learning community",
      "Instructors improving engagement and completion"],
  },
  "Home & DIY": {
    "Moving & Relocation": [
      "People planning and organizing a move",
      "First-time renters setting up a place",
      "People downsizing their home"],
    "Sustainable & Self-Sufficient Living": [
      "People reducing household waste",
      "People starting composting or solar",
      "Beginner homesteaders"],
  },
  "Pets & Animal Care": {
    "Pet Content & Community": [
      "Pet owners growing a pet social account",
      "Pet-brand affiliates and ambassadors",
      "Pet creators monetizing an audience"],
  },
  "Hobbies & Creative Skills": {
    "Photography": [
      "Beginners learning manual mode",
      "Hobbyists learning photo editing",
      "People starting a photography side-gig"],
    "Collecting & Restoration": [
      "Collectors cataloguing a collection",
      "People restoring furniture or cars",
      "Hobbyists valuing and trading items"],
  },
  "Productivity & Self-Organization": {
    "Focus & Deep Work": [
      "Knowledge workers reducing distraction",
      "People building focus rituals",
      "People managing digital overwhelm"],
  },
  "Technology & Software": {
    "Cybersecurity & Privacy": [
      "Individuals locking down their accounts",
      "Small businesses handling basic security",
      "Aspiring security-certification candidates"],
  },
  "Food & Culinary": {
    "Restaurant & Food Service": [
      "Small restaurant owners managing costs",
      "Food-truck operators starting out",
      "Cafe owners improving margins"],
  },
}

# ---- 10 new markets (Tier 1 + Tier 2) ----
_NEW_MARKETS = {
  "Trading, Investing & Crypto": {
    "description": "Active trading, self-directed investing, and market education — distinct from everyday budgeting/saving.",
    "submarkets": {
      "Stock Trading": [
        "Beginner day traders learning the basics",
        "Swing traders building a repeatable system",
        "Traders journaling and reviewing their trades"],
      "Options Trading": [
        "Beginners learning how options work",
        "Income-focused options sellers",
        "Options traders managing risk and Greeks"],
      "Crypto Investing": [
        "First-time crypto buyers",
        "Long-term DCA holders",
        "People setting up self-custody wallets safely"],
      "Crypto Trading & DeFi": [
        "Active crypto traders",
        "DeFi users chasing yield",
        "On-chain / airdrop hunters"],
      "Technical & Chart Analysis": [
        "People learning to read charts and patterns",
        "Traders building and managing watchlists",
        "People backtesting a strategy"],
      "Trading Psychology & Risk": [
        "Traders struggling with discipline",
        "People recovering from big losses / tilt",
        "Traders learning position sizing"],
      "Investing Research & Tools": [
        "DIY investors researching individual stocks",
        "Investors building a portfolio tracker",
        "Dividend and income investors"],
    }},
  "AI Tools & Automation": {
    "description": "Applying AI tools, prompting, and automation to real work — for non-engineers, creators, and operators.",
    "submarkets": {
      "AI for Business Owners": [
        "Owners using AI to cut admin time",
        "Teams adopting AI tools day-to-day",
        "Businesses writing an internal AI policy"],
      "AI Content Workflows": [
        "Creators using AI for ideation and scripting",
        "Marketers generating content at scale",
        "Writers editing and refining with AI"],
      "Prompting & LLM Skills": [
        "People learning to write better prompts",
        "People building reusable prompt libraries",
        "Professionals upskilling on ChatGPT for their job"],
      "AI Agents & Assistants": [
        "People building custom GPTs",
        "Makers building autonomous AI agents",
        "People automating tasks with AI assistants"],
      "No-Code AI Automation": [
        "People connecting AI into their existing tools",
        "Ops people automating manual workflows",
        "Agencies building AI systems for clients"],
      "AI for Creators & Media": [
        "AI image and video creators",
        "Operators of faceless AI channels",
        "People using AI voice and avatars"],
      "AI Literacy & Careers": [
        "Non-technical professionals staying relevant",
        "People learning AI skills for their current role",
        "Career switchers moving toward AI work"],
    }},
  "Reselling, Flipping & Arbitrage": {
    "description": "Buying and reselling goods for profit as an income stream — sourcing, channels, and operations.",
    "submarkets": {
      "Sneaker & Streetwear Reselling": [
        "Beginner sneaker resellers",
        "Resellers using monitors and release tools",
        "Resellers managing inventory and cashflow"],
      "Retail & Online Arbitrage": [
        "Retail-arbitrage sourcers",
        "Online-arbitrage sellers",
        "People scaling Amazon arbitrage"],
      "Thrift & Vintage Flipping": [
        "Thrift flippers on eBay / Poshmark",
        "Vintage-clothing resellers",
        "People sourcing at estate and garage sales"],
      "Collectibles & Trading Cards": [
        "Trading-card flippers and breakers",
        "Comic and collectible investors",
        "People grading and reselling items"],
      "Wholesale & Liquidation": [
        "Sellers buying liquidation pallets",
        "Wholesale sourcers building supplier lists",
        "People reselling bulk lots"],
      "Ticket & Event Reselling": [
        "Event-ticket resellers",
        "Resellers navigating platform rules",
        "Resellers managing pricing risk"],
      "Reseller Operations & Tools": [
        "Resellers tracking profit and inventory",
        "Resellers automating cross-listing",
        "Resellers handling shipping and returns"],
    }},
  "Digital Marketing & Agencies": {
    "description": "Marketing as a profession and agency service — distinct from a local owner marketing their own shop.",
    "submarkets": {
      "Social Media Marketing (SMMA)": [
        "People starting a social-media agency",
        "Agencies landing their first clients",
        "Freelancers managing client social accounts"],
      "Paid Advertising": [
        "People running their first Meta ads",
        "Google Ads managers",
        "Media buyers scaling ad budgets"],
      "SEO & Content Marketing": [
        "People learning SEO fundamentals",
        "Content marketers building topical authority",
        "Local-SEO specialists"],
      "Email Marketing": [
        "Email marketers building automated flows",
        "Marketers growing and cleaning lists",
        "Marketers improving deliverability"],
      "Lead Generation & Cold Outreach": [
        "People building cold-email systems",
        "Lead-gen agency operators",
        "Appointment setters booking calls"],
      "Conversion Rate Optimization": [
        "Marketers A/B testing landing pages",
        "People fixing leaky funnels",
        "CRO specialists improving checkout"],
      "Agency Operations & Scaling": [
        "Agency owners systematizing delivery",
        "Agencies hiring and onboarding",
        "Owners productizing their services"],
    }},
  "Self-Improvement & Personal Development": {
    "description": "Mindset, discipline, and life design — the identity/motivation layer, distinct from clinical health or productivity tooling.",
    "submarkets": {
      "Discipline & Habits": [
        "People building lasting self-discipline",
        "People who start habits but can't sustain them",
        "People designing an identity-based routine"],
      "Mindset & Confidence": [
        "People building genuine self-confidence",
        "People overcoming chronic self-doubt",
        "People reframing limiting beliefs"],
      "Focus & Motivation": [
        "People chronically procrastinating",
        "People struggling to find motivation",
        "People recovering from burnout"],
      "Purpose & Life Design": [
        "People clarifying goals and values",
        "People intentionally designing their life",
        "People navigating a quarter-life crisis"],
      "Social Skills & Charisma": [
        "People improving everyday conversation",
        "People building presence and charisma",
        "Introverts developing social confidence"],
      "Learning & Memory": [
        "People trying to learn skills faster",
        "People improving memory and retention",
        "People building a consistent reading habit"],
      "Emotional Regulation & Resilience": [
        "People learning to manage their emotions",
        "People building resilience to setbacks",
        "People handling stress more mindfully"],
    }},
  "Sales & Closing": {
    "description": "The sales profession — closing, setting, prospecting, and building sales processes.",
    "submarkets": {
      "High-Ticket Closing": [
        "Aspiring remote closers",
        "Closers landing their first offer",
        "Closers improving their close rate"],
      "Appointment Setting": [
        "People starting as appointment setters",
        "Setters trying to book more qualified calls",
        "Teams managing setter workflows"],
      "B2B & SaaS Sales": [
        "SDRs / BDRs prospecting effectively",
        "Account execs running discovery calls",
        "Reps managing a pipeline"],
      "Cold Outreach & Prospecting": [
        "Reps writing cold emails and DMs",
        "People building targeted prospect lists",
        "Reps handling objections and follow-up"],
      "Sales Skills & Psychology": [
        "People learning to handle objections",
        "Reps improving discovery and questioning",
        "People building rapport and trust fast"],
      "Sales Management & Teams": [
        "New sales managers",
        "Owners building a repeatable sales process",
        "Teams adopting and using a CRM"],
    }},
  "Gaming & Esports": {
    "description": "Playing, coaching, streaming, and building businesses around games.",
    "submarkets": {
      "Game Coaching & Improvement": [
        "Players trying to rank up in a specific game",
        "Aspiring coaches monetizing their skill",
        "Players reviewing and improving their gameplay"],
      "Streaming & Content": [
        "New Twitch / YouTube streamers",
        "Streamers trying to grow viewership",
        "Streamers monetizing their stream"],
      "Esports & Competitive": [
        "Aspiring pro players",
        "Amateur team organizers",
        "Competitive players structuring practice"],
      "Indie Game Development": [
        "Solo devs shipping a first game",
        "Hobbyists learning a game engine",
        "Indie devs marketing their game"],
      "Gaming Communities & Servers": [
        "Discord community owners",
        "Server moderators managing members",
        "People monetizing a gaming community"],
      "Gaming Services & Business": [
        "People selling coaching or in-game services",
        "Gaming-gear affiliates and reviewers",
        "People building a gaming brand"],
    }},
  "Music & Audio Production": {
    "description": "Making, mixing, releasing, and monetizing music and audio.",
    "submarkets": {
      "Music Production & Beatmaking": [
        "Beginner producers learning a DAW",
        "Beatmakers selling beats online",
        "Producers who can't finish tracks"],
      "Mixing & Mastering": [
        "People learning to mix their own music",
        "Home-studio engineers",
        "People mastering tracks for release"],
      "Songwriting & Composition": [
        "Songwriters finishing more songs",
        "People writing toplines and lyrics",
        "Composers scoring for media"],
      "Selling Music Assets": [
        "Sample-pack creators",
        "Preset and sound-kit sellers",
        "Producers licensing their beats"],
      "Artist Growth & Release": [
        "Independent artists releasing music",
        "Artists growing on streaming platforms",
        "Artists building a real fanbase"],
      "Audio & Podcast Production": [
        "Podcast editors for creators",
        "Audio engineers for online content",
        "People improving home-recording quality"],
    }},
  "Writing & Publishing": {
    "description": "The writing crafts and getting written work published or sold — distinct from generic freelancing.",
    "submarkets": {
      "Self-Publishing (KDP)": [
        "First-time self-publishers",
        "KDP authors marketing their books",
        "Low-content / no-content book publishers"],
      "Fiction Writing": [
        "Aspiring novelists finishing a first draft",
        "Writers learning to self-edit",
        "Authors building a series and readership"],
      "Nonfiction & Authority Books": [
        "Experts writing an authority book",
        "People outlining and structuring nonfiction",
        "Authors using a book to attract clients"],
      "Copywriting": [
        "Beginner copywriters landing first clients",
        "Copywriters building a portfolio",
        "People learning direct-response copy"],
      "Ghostwriting": [
        "Ghostwriters landing clients",
        "LinkedIn / X ghostwriters",
        "People packaging a ghostwriting service"],
      "Blogging & Content Writing": [
        "Bloggers trying to monetize",
        "Freelance content and SEO writers",
        "Writers building a body of work"],
    }},
  "Design & Templates": {
    "description": "Design as a product and a service — sellable templates plus client design work.",
    "submarkets": {
      "Notion & Productivity Templates": [
        "Notion template creators",
        "People selling productivity systems",
        "Template shop owners"],
      "Canva & Social Templates": [
        "Canva template sellers",
        "People making social-media templates",
        "Designers selling brand kits"],
      "Graphic Design Services": [
        "Freelance graphic designers finding clients",
        "Designers pricing their work",
        "Designers building a service offer"],
      "Web & UX/UI Design": [
        "Aspiring UX designers building a portfolio",
        "Web designers landing clients",
        "People learning Figma"],
      "Printables & Digital Products": [
        "Printable-planner sellers",
        "Digital-download shop designers",
        "People creating journals and workbooks"],
      "Brand & Identity Design": [
        "People building a brand identity",
        "Logo designers",
        "Designers creating brand guidelines"],
      "Design Assets & Tools": [
        "Creators selling mockups and assets",
        "People building icon and font packs",
        "Designers automating work with templates"],
    }},
}


def _merge_seed():
    """Combine the untouched base taxonomy with the V1 expansion.
    Base entries (and their IDs) are preserved; deepening adds new submarkets;
    new markets are appended."""
    out = {name: {"description": d["description"], "submarkets": dict(d["submarkets"])}
           for name, d in _BASE.items()}
    for mname, subs in _EXPANSION_SUBMARKETS.items():
        if mname not in out:
            raise KeyError(f"expansion targets unknown market: {mname}")
        for sname, auds in subs.items():
            if sname in out[mname]["submarkets"]:
                raise KeyError(f"submarket collision in {mname}: {sname}")
            out[mname]["submarkets"][sname] = auds
    for mname, d in _NEW_MARKETS.items():
        if mname in out:
            raise KeyError(f"new market collides with existing: {mname}")
        out[mname] = {"description": d["description"], "submarkets": d["submarkets"]}
    return out


SEED = _merge_seed()
