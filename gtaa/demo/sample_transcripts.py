"""
Sample Genesys Cloud transcripts in the exact Speech & Text Analytics JSON format.
These represent realistic call center scenarios for demo/testing purposes.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from gtaa.genesys.conversations import ConversationSummary
from gtaa.genesys.transcripts import Transcript, TranscriptTurn


# ---------------------------------------------------------------------------
# Raw JSON matching the Genesys Speech & Text Analytics transcript format
# (same structure as returned by the pre-signed S3 URL)
# ---------------------------------------------------------------------------

SAMPLE_TRANSCRIPT_JSONS: List[dict] = [
    # ------------------------------------------------------------------
    # 1. Billing dispute — frustrated customer
    # ------------------------------------------------------------------
    {
        "_conversation_meta": {
            "conversation_id": "a1b2c3d4-0001-0000-0000-000000000001",
            "queue": "Billing Support",
            "start_time": "2025-03-10T14:05:00Z",
            "duration_ms": 312000,
        },
        "transcripts": [
            {
                "phrases": [
                    {"channel": 1, "participantPurpose": "agent",   "offsetMs": 0,      "durationMs": 3200,  "words": [{"word": "Thank"}, {"word": "you"}, {"word": "for"}, {"word": "calling"}, {"word": "Acme"}, {"word": "Bank,"}, {"word": "my"}, {"word": "name"}, {"word": "is"}, {"word": "Sarah,"}, {"word": "how"}, {"word": "can"}, {"word": "I"}, {"word": "help"}, {"word": "you"}, {"word": "today?"}]},
                    {"channel": 0, "participantPurpose": "customer", "offsetMs": 3500,   "durationMs": 5800,  "words": [{"word": "Hi,"}, {"word": "yes,"}, {"word": "I'm"}, {"word": "calling"}, {"word": "because"}, {"word": "I"}, {"word": "was"}, {"word": "charged"}, {"word": "twice"}, {"word": "on"}, {"word": "my"}, {"word": "account"}, {"word": "this"}, {"word": "month."}, {"word": "I"}, {"word": "have"}, {"word": "a"}, {"word": "charge"}, {"word": "for"}, {"word": "two"}, {"word": "hundred"}, {"word": "and"}, {"word": "fifty"}, {"word": "dollars"}, {"word": "that"}, {"word": "I"}, {"word": "don't"}, {"word": "recognize."}]},
                    {"channel": 1, "participantPurpose": "agent",   "offsetMs": 9500,   "durationMs": 3000,  "words": [{"word": "I"}, {"word": "understand"}, {"word": "your"}, {"word": "concern."}, {"word": "Can"}, {"word": "I"}, {"word": "have"}, {"word": "your"}, {"word": "account"}, {"word": "number"}, {"word": "to"}, {"word": "look"}, {"word": "into"}, {"word": "this?"}]},
                    {"channel": 0, "participantPurpose": "customer", "offsetMs": 12800,  "durationMs": 2500,  "words": [{"word": "Yes,"}, {"word": "it's"}, {"word": "four"}, {"word": "four"}, {"word": "seven"}, {"word": "eight"}, {"word": "dash"}, {"word": "nine"}, {"word": "nine"}, {"word": "two"}, {"word": "one."}]},
                    {"channel": 1, "participantPurpose": "agent",   "offsetMs": 15500,  "durationMs": 6000,  "words": [{"word": "Thank"}, {"word": "you."}, {"word": "I"}, {"word": "can"}, {"word": "see"}, {"word": "your"}, {"word": "account"}, {"word": "here."}, {"word": "I"}, {"word": "can"}, {"word": "see"}, {"word": "there"}, {"word": "are"}, {"word": "two"}, {"word": "charges"}, {"word": "of"}, {"word": "two"}, {"word": "hundred"}, {"word": "fifty"}, {"word": "on"}, {"word": "March"}, {"word": "fifth"}, {"word": "and"}, {"word": "March"}, {"word": "sixth."}]},
                    {"channel": 0, "participantPurpose": "customer", "offsetMs": 21700,  "durationMs": 4000,  "words": [{"word": "Exactly!"}, {"word": "I"}, {"word": "only"}, {"word": "made"}, {"word": "one"}, {"word": "purchase"}, {"word": "at"}, {"word": "the"}, {"word": "grocery"}, {"word": "store"}, {"word": "on"}, {"word": "the"}, {"word": "fifth."}, {"word": "The"}, {"word": "second"}, {"word": "one"}, {"word": "is"}, {"word": "a"}, {"word": "complete"}, {"word": "mistake."}]},
                    {"channel": 1, "participantPurpose": "agent",   "offsetMs": 26000,  "durationMs": 5500,  "words": [{"word": "I"}, {"word": "completely"}, {"word": "understand"}, {"word": "and"}, {"word": "I"}, {"word": "apologize"}, {"word": "for"}, {"word": "the"}, {"word": "inconvenience."}, {"word": "I'm"}, {"word": "going"}, {"word": "to"}, {"word": "initiate"}, {"word": "a"}, {"word": "dispute"}, {"word": "for"}, {"word": "the"}, {"word": "duplicate"}, {"word": "charge."}, {"word": "It"}, {"word": "will"}, {"word": "be"}, {"word": "credited"}, {"word": "within"}, {"word": "three"}, {"word": "to"}, {"word": "five"}, {"word": "business"}, {"word": "days."}]},
                    {"channel": 0, "participantPurpose": "customer", "offsetMs": 31800,  "durationMs": 2800,  "words": [{"word": "Okay,"}, {"word": "that"}, {"word": "sounds"}, {"word": "good."}, {"word": "Do"}, {"word": "I"}, {"word": "need"}, {"word": "to"}, {"word": "do"}, {"word": "anything"}, {"word": "else?"}]},
                    {"channel": 1, "participantPurpose": "agent",   "offsetMs": 34800,  "durationMs": 4200,  "words": [{"word": "No,"}, {"word": "everything"}, {"word": "has"}, {"word": "been"}, {"word": "taken"}, {"word": "care"}, {"word": "of."}, {"word": "You"}, {"word": "will"}, {"word": "receive"}, {"word": "a"}, {"word": "confirmation"}, {"word": "email"}, {"word": "shortly."}, {"word": "Is"}, {"word": "there"}, {"word": "anything"}, {"word": "else"}, {"word": "I"}, {"word": "can"}, {"word": "help"}, {"word": "you"}, {"word": "with?"}]},
                    {"channel": 0, "participantPurpose": "customer", "offsetMs": 39200,  "durationMs": 1800,  "words": [{"word": "No,"}, {"word": "that"}, {"word": "will"}, {"word": "be"}, {"word": "all."}, {"word": "Thanks"}, {"word": "Sarah."}]},
                    {"channel": 1, "participantPurpose": "agent",   "offsetMs": 41200,  "durationMs": 2000,  "words": [{"word": "You're"}, {"word": "welcome."}, {"word": "Have"}, {"word": "a"}, {"word": "great"}, {"word": "day!"}]},
                ]
            }
        ]
    },

    # ------------------------------------------------------------------
    # 2. Technical support — internet outage
    # ------------------------------------------------------------------
    {
        "_conversation_meta": {
            "conversation_id": "a1b2c3d4-0002-0000-0000-000000000002",
            "queue": "Technical Support",
            "start_time": "2025-03-11T09:22:00Z",
            "duration_ms": 487000,
        },
        "transcripts": [
            {
                "phrases": [
                    {"channel": 1, "participantPurpose": "agent",   "offsetMs": 0,      "durationMs": 3000,  "words": [{"word": "Technical"}, {"word": "support,"}, {"word": "this"}, {"word": "is"}, {"word": "James."}, {"word": "How"}, {"word": "can"}, {"word": "I"}, {"word": "assist"}, {"word": "you?"}]},
                    {"channel": 0, "participantPurpose": "customer", "offsetMs": 3200,   "durationMs": 6500,  "words": [{"word": "Hi"}, {"word": "James,"}, {"word": "I've"}, {"word": "been"}, {"word": "without"}, {"word": "internet"}, {"word": "for"}, {"word": "the"}, {"word": "past"}, {"word": "two"}, {"word": "hours."}, {"word": "I"}, {"word": "work"}, {"word": "from"}, {"word": "home"}, {"word": "and"}, {"word": "this"}, {"word": "is"}, {"word": "really"}, {"word": "affecting"}, {"word": "my"}, {"word": "productivity."}]},
                    {"channel": 1, "participantPurpose": "agent",   "offsetMs": 10000,  "durationMs": 2500,  "words": [{"word": "I"}, {"word": "sincerely"}, {"word": "apologize"}, {"word": "for"}, {"word": "that."}, {"word": "Can"}, {"word": "you"}, {"word": "tell"}, {"word": "me"}, {"word": "your"}, {"word": "service"}, {"word": "address?"}]},
                    {"channel": 0, "participantPurpose": "customer", "offsetMs": 12700,  "durationMs": 3000,  "words": [{"word": "Sure,"}, {"word": "it's"}, {"word": "four"}, {"word": "twenty"}, {"word": "two"}, {"word": "Oak"}, {"word": "Street,"}, {"word": "Springfield."}]},
                    {"channel": 1, "participantPurpose": "agent",   "offsetMs": 16000,  "durationMs": 8000,  "words": [{"word": "I"}, {"word": "can"}, {"word": "see"}, {"word": "your"}, {"word": "address."}, {"word": "There"}, {"word": "is"}, {"word": "actually"}, {"word": "a"}, {"word": "known"}, {"word": "outage"}, {"word": "in"}, {"word": "your"}, {"word": "area"}, {"word": "due"}, {"word": "to"}, {"word": "a"}, {"word": "fiber"}, {"word": "cut."}, {"word": "Our"}, {"word": "technicians"}, {"word": "are"}, {"word": "working"}, {"word": "on"}, {"word": "it"}, {"word": "and"}, {"word": "the"}, {"word": "estimated"}, {"word": "restoration"}, {"word": "time"}, {"word": "is"}, {"word": "two"}, {"word": "PM."}]},
                    {"channel": 0, "participantPurpose": "customer", "offsetMs": 24200,  "durationMs": 4500,  "words": [{"word": "Two"}, {"word": "PM?"}, {"word": "That's"}, {"word": "still"}, {"word": "three"}, {"word": "more"}, {"word": "hours!"}, {"word": "Is"}, {"word": "there"}, {"word": "anything"}, {"word": "you"}, {"word": "can"}, {"word": "do"}, {"word": "to"}, {"word": "speed"}, {"word": "this"}, {"word": "up?"}, {"word": "I"}, {"word": "have"}, {"word": "meetings."}]},
                    {"channel": 1, "participantPurpose": "agent",   "offsetMs": 29000,  "durationMs": 5500,  "words": [{"word": "I"}, {"word": "completely"}, {"word": "understand"}, {"word": "your"}, {"word": "frustration."}, {"word": "Unfortunately"}, {"word": "I"}, {"word": "cannot"}, {"word": "speed"}, {"word": "up"}, {"word": "the"}, {"word": "repair."}, {"word": "However,"}, {"word": "I"}, {"word": "can"}, {"word": "credit"}, {"word": "your"}, {"word": "account"}, {"word": "for"}, {"word": "one"}, {"word": "day"}, {"word": "of"}, {"word": "service"}, {"word": "as"}, {"word": "compensation."}]},
                    {"channel": 0, "participantPurpose": "customer", "offsetMs": 34700,  "durationMs": 2000,  "words": [{"word": "Okay,"}, {"word": "I"}, {"word": "guess"}, {"word": "that"}, {"word": "helps"}, {"word": "a"}, {"word": "bit."}, {"word": "Will"}, {"word": "I"}, {"word": "get"}, {"word": "notified"}, {"word": "when"}, {"word": "it's"}, {"word": "back?"}]},
                    {"channel": 1, "participantPurpose": "agent",   "offsetMs": 36900,  "durationMs": 3500,  "words": [{"word": "Yes,"}, {"word": "I'll"}, {"word": "set"}, {"word": "up"}, {"word": "an"}, {"word": "SMS"}, {"word": "notification"}, {"word": "to"}, {"word": "your"}, {"word": "phone"}, {"word": "number"}, {"word": "on"}, {"word": "file."}, {"word": "You'll"}, {"word": "receive"}, {"word": "a"}, {"word": "text"}, {"word": "as"}, {"word": "soon"}, {"word": "as"}, {"word": "service"}, {"word": "is"}, {"word": "restored."}]},
                    {"channel": 0, "participantPurpose": "customer", "offsetMs": 40600,  "durationMs": 1500,  "words": [{"word": "That"}, {"word": "would"}, {"word": "be"}, {"word": "great."}, {"word": "Thank"}, {"word": "you."}]},
                    {"channel": 1, "participantPurpose": "agent",   "offsetMs": 42300,  "durationMs": 2200,  "words": [{"word": "You're"}, {"word": "welcome."}, {"word": "We"}, {"word": "apologize"}, {"word": "for"}, {"word": "the"}, {"word": "inconvenience."}, {"word": "Is"}, {"word": "there"}, {"word": "anything"}, {"word": "else?"}]},
                    {"channel": 0, "participantPurpose": "customer", "offsetMs": 44700,  "durationMs": 1200,  "words": [{"word": "No,"}, {"word": "that's"}, {"word": "all."}, {"word": "Goodbye."}]},
                ]
            }
        ]
    },

    # ------------------------------------------------------------------
    # 3. Cancelation attempt — retention scenario
    # ------------------------------------------------------------------
    {
        "_conversation_meta": {
            "conversation_id": "a1b2c3d4-0003-0000-0000-000000000003",
            "queue": "Customer Retention",
            "start_time": "2025-03-12T16:45:00Z",
            "duration_ms": 623000,
        },
        "transcripts": [
            {
                "phrases": [
                    {"channel": 1, "participantPurpose": "agent",   "offsetMs": 0,      "durationMs": 3000,  "words": [{"word": "Hello,"}, {"word": "thanks"}, {"word": "for"}, {"word": "calling"}, {"word": "StreamPlus."}, {"word": "This"}, {"word": "is"}, {"word": "Maria."}, {"word": "How"}, {"word": "can"}, {"word": "I"}, {"word": "help?"}]},
                    {"channel": 0, "participantPurpose": "customer", "offsetMs": 3300,   "durationMs": 4500,  "words": [{"word": "Hi"}, {"word": "Maria,"}, {"word": "I"}, {"word": "want"}, {"word": "to"}, {"word": "cancel"}, {"word": "my"}, {"word": "subscription."}, {"word": "I've"}, {"word": "been"}, {"word": "a"}, {"word": "customer"}, {"word": "for"}, {"word": "three"}, {"word": "years"}, {"word": "but"}, {"word": "the"}, {"word": "price"}, {"word": "keeps"}, {"word": "going"}, {"word": "up."}]},
                    {"channel": 1, "participantPurpose": "agent",   "offsetMs": 8000,   "durationMs": 3500,  "words": [{"word": "I'm"}, {"word": "sorry"}, {"word": "to"}, {"word": "hear"}, {"word": "that."}, {"word": "I"}, {"word": "value"}, {"word": "your"}, {"word": "loyalty."}, {"word": "Can"}, {"word": "you"}, {"word": "tell"}, {"word": "me"}, {"word": "more"}, {"word": "about"}, {"word": "your"}, {"word": "concerns?"}]},
                    {"channel": 0, "participantPurpose": "customer", "offsetMs": 11700,  "durationMs": 5000,  "words": [{"word": "Well,"}, {"word": "I"}, {"word": "started"}, {"word": "at"}, {"word": "nine"}, {"word": "ninety"}, {"word": "nine"}, {"word": "a"}, {"word": "month"}, {"word": "and"}, {"word": "now"}, {"word": "I'm"}, {"word": "paying"}, {"word": "fifteen"}, {"word": "ninety"}, {"word": "nine."}, {"word": "That's"}, {"word": "a"}, {"word": "sixty"}, {"word": "percent"}, {"word": "increase."}, {"word": "Plus"}, {"word": "I"}, {"word": "barely"}, {"word": "use"}, {"word": "it"}, {"word": "anymore."}]},
                    {"channel": 1, "participantPurpose": "agent",   "offsetMs": 17000,  "durationMs": 4500,  "words": [{"word": "I"}, {"word": "completely"}, {"word": "understand."}, {"word": "As"}, {"word": "a"}, {"word": "loyal"}, {"word": "customer"}, {"word": "of"}, {"word": "three"}, {"word": "years,"}, {"word": "I"}, {"word": "would"}, {"word": "like"}, {"word": "to"}, {"word": "offer"}, {"word": "you"}, {"word": "our"}, {"word": "reduced"}, {"word": "plan"}, {"word": "at"}, {"word": "seven"}, {"word": "ninety"}, {"word": "nine"}, {"word": "a"}, {"word": "month"}, {"word": "for"}, {"word": "the"}, {"word": "next"}, {"word": "six"}, {"word": "months."}]},
                    {"channel": 0, "participantPurpose": "customer", "offsetMs": 21700,  "durationMs": 3000,  "words": [{"word": "Hmm,"}, {"word": "that's"}, {"word": "interesting."}, {"word": "Does"}, {"word": "it"}, {"word": "include"}, {"word": "all"}, {"word": "the"}, {"word": "same"}, {"word": "content?"}]},
                    {"channel": 1, "participantPurpose": "agent",   "offsetMs": 24900,  "durationMs": 4000,  "words": [{"word": "Yes,"}, {"word": "it"}, {"word": "includes"}, {"word": "all"}, {"word": "the"}, {"word": "same"}, {"word": "movies,"}, {"word": "shows,"}, {"word": "and"}, {"word": "four"}, {"word": "K"}, {"word": "streaming."}, {"word": "After"}, {"word": "six"}, {"word": "months"}, {"word": "it"}, {"word": "would"}, {"word": "go"}, {"word": "to"}, {"word": "eleven"}, {"word": "ninety"}, {"word": "nine."}]},
                    {"channel": 0, "participantPurpose": "customer", "offsetMs": 29100,  "durationMs": 3500,  "words": [{"word": "That"}, {"word": "actually"}, {"word": "sounds"}, {"word": "reasonable."}, {"word": "Can"}, {"word": "I"}, {"word": "also"}, {"word": "pause"}, {"word": "the"}, {"word": "account"}, {"word": "for"}, {"word": "a"}, {"word": "month"}, {"word": "if"}, {"word": "I"}, {"word": "travel?"}]},
                    {"channel": 1, "participantPurpose": "agent",   "offsetMs": 32800,  "durationMs": 2500,  "words": [{"word": "Absolutely!"}, {"word": "You"}, {"word": "can"}, {"word": "pause"}, {"word": "for"}, {"word": "up"}, {"word": "to"}, {"word": "three"}, {"word": "months"}, {"word": "per"}, {"word": "year"}, {"word": "at"}, {"word": "no"}, {"word": "charge."}]},
                    {"channel": 0, "participantPurpose": "customer", "offsetMs": 35500,  "durationMs": 2500,  "words": [{"word": "Okay,"}, {"word": "you"}, {"word": "know"}, {"word": "what,"}, {"word": "let's"}, {"word": "go"}, {"word": "with"}, {"word": "the"}, {"word": "discounted"}, {"word": "plan."}, {"word": "I'll"}, {"word": "keep"}, {"word": "the"}, {"word": "service."}]},
                    {"channel": 1, "participantPurpose": "agent",   "offsetMs": 38200,  "durationMs": 3000,  "words": [{"word": "Wonderful!"}, {"word": "I've"}, {"word": "applied"}, {"word": "the"}, {"word": "discount."}, {"word": "You'll"}, {"word": "see"}, {"word": "the"}, {"word": "new"}, {"word": "rate"}, {"word": "on"}, {"word": "your"}, {"word": "next"}, {"word": "bill."}, {"word": "Thank"}, {"word": "you"}, {"word": "for"}, {"word": "staying"}, {"word": "with"}, {"word": "us!"}]},
                ]
            }
        ]
    },

    # ------------------------------------------------------------------
    # 4. Healthcare appointment — scheduling
    # ------------------------------------------------------------------
    {
        "_conversation_meta": {
            "conversation_id": "a1b2c3d4-0004-0000-0000-000000000004",
            "queue": "Appointments",
            "start_time": "2025-03-13T08:10:00Z",
            "duration_ms": 258000,
        },
        "transcripts": [
            {
                "phrases": [
                    {"channel": 1, "participantPurpose": "agent",   "offsetMs": 0,      "durationMs": 2800,  "words": [{"word": "Good"}, {"word": "morning,"}, {"word": "City"}, {"word": "Medical"}, {"word": "Center,"}, {"word": "this"}, {"word": "is"}, {"word": "Dr."}, {"word": "Wilson's"}, {"word": "office."}]},
                    {"channel": 0, "participantPurpose": "customer", "offsetMs": 3000,   "durationMs": 4000,  "words": [{"word": "Good"}, {"word": "morning."}, {"word": "I"}, {"word": "need"}, {"word": "to"}, {"word": "reschedule"}, {"word": "my"}, {"word": "appointment."}, {"word": "It's"}, {"word": "currently"}, {"word": "for"}, {"word": "this"}, {"word": "Thursday"}, {"word": "at"}, {"word": "two"}, {"word": "PM."}]},
                    {"channel": 1, "participantPurpose": "agent",   "offsetMs": 7200,   "durationMs": 2000,  "words": [{"word": "Of"}, {"word": "course."}, {"word": "May"}, {"word": "I"}, {"word": "have"}, {"word": "your"}, {"word": "name"}, {"word": "and"}, {"word": "date"}, {"word": "of"}, {"word": "birth?"}]},
                    {"channel": 0, "participantPurpose": "customer", "offsetMs": 9400,   "durationMs": 2500,  "words": [{"word": "Robert"}, {"word": "Thompson,"}, {"word": "April"}, {"word": "twelfth,"}, {"word": "nineteen"}, {"word": "seventy"}, {"word": "eight."}]},
                    {"channel": 1, "participantPurpose": "agent",   "offsetMs": 12100,  "durationMs": 3000,  "words": [{"word": "Found"}, {"word": "it."}, {"word": "You're"}, {"word": "scheduled"}, {"word": "for"}, {"word": "a"}, {"word": "routine"}, {"word": "check-up."}, {"word": "What"}, {"word": "date"}, {"word": "works"}, {"word": "better"}, {"word": "for"}, {"word": "you?"}]},
                    {"channel": 0, "participantPurpose": "customer", "offsetMs": 15300,  "durationMs": 3000,  "words": [{"word": "Would"}, {"word": "next"}, {"word": "Tuesday"}, {"word": "morning"}, {"word": "be"}, {"word": "possible?"}, {"word": "Before"}, {"word": "eleven"}, {"word": "if"}, {"word": "you"}, {"word": "have"}, {"word": "anything."}]},
                    {"channel": 1, "participantPurpose": "agent",   "offsetMs": 18500,  "durationMs": 3500,  "words": [{"word": "Yes,"}, {"word": "I"}, {"word": "have"}, {"word": "nine"}, {"word": "thirty"}, {"word": "or"}, {"word": "ten"}, {"word": "fifteen"}, {"word": "available"}, {"word": "on"}, {"word": "Tuesday."}]},
                    {"channel": 0, "participantPurpose": "customer", "offsetMs": 22200,  "durationMs": 1500,  "words": [{"word": "Ten"}, {"word": "fifteen"}, {"word": "works"}, {"word": "perfectly."}]},
                    {"channel": 1, "participantPurpose": "agent",   "offsetMs": 24000,  "durationMs": 3000,  "words": [{"word": "Perfect."}, {"word": "I've"}, {"word": "rescheduled"}, {"word": "you"}, {"word": "for"}, {"word": "Tuesday"}, {"word": "at"}, {"word": "ten"}, {"word": "fifteen"}, {"word": "AM."}, {"word": "You'll"}, {"word": "receive"}, {"word": "a"}, {"word": "reminder"}, {"word": "the"}, {"word": "day"}, {"word": "before."}]},
                    {"channel": 0, "participantPurpose": "customer", "offsetMs": 27200,  "durationMs": 1500,  "words": [{"word": "Great,"}, {"word": "thank"}, {"word": "you"}, {"word": "very"}, {"word": "much."}]},
                    {"channel": 1, "participantPurpose": "agent",   "offsetMs": 28900,  "durationMs": 1800,  "words": [{"word": "Have"}, {"word": "a"}, {"word": "wonderful"}, {"word": "day,"}, {"word": "Mr."}, {"word": "Thompson."}]},
                ]
            }
        ]
    },

    # ------------------------------------------------------------------
    # 5. E-commerce — damaged product complaint (escalation)
    # ------------------------------------------------------------------
    {
        "_conversation_meta": {
            "conversation_id": "a1b2c3d4-0005-0000-0000-000000000005",
            "queue": "Customer Service",
            "start_time": "2025-03-14T11:30:00Z",
            "duration_ms": 542000,
        },
        "transcripts": [
            {
                "phrases": [
                    {"channel": 1, "participantPurpose": "agent",   "offsetMs": 0,      "durationMs": 3000,  "words": [{"word": "Hello,"}, {"word": "you've"}, {"word": "reached"}, {"word": "ShopFast"}, {"word": "customer"}, {"word": "service."}, {"word": "My"}, {"word": "name"}, {"word": "is"}, {"word": "Alex."}]},
                    {"channel": 0, "participantPurpose": "customer", "offsetMs": 3300,   "durationMs": 6000,  "words": [{"word": "Hi"}, {"word": "Alex."}, {"word": "I"}, {"word": "received"}, {"word": "my"}, {"word": "order"}, {"word": "yesterday"}, {"word": "and"}, {"word": "the"}, {"word": "TV"}, {"word": "was"}, {"word": "completely"}, {"word": "smashed."}, {"word": "The"}, {"word": "box"}, {"word": "looked"}, {"word": "like"}, {"word": "it"}, {"word": "was"}, {"word": "dropped"}, {"word": "from"}, {"word": "a"}, {"word": "truck."}]},
                    {"channel": 1, "participantPurpose": "agent",   "offsetMs": 9600,   "durationMs": 2500,  "words": [{"word": "Oh"}, {"word": "no,"}, {"word": "I'm"}, {"word": "so"}, {"word": "sorry"}, {"word": "to"}, {"word": "hear"}, {"word": "that!"}, {"word": "Can"}, {"word": "I"}, {"word": "get"}, {"word": "your"}, {"word": "order"}, {"word": "number?"}]},
                    {"channel": 0, "participantPurpose": "customer", "offsetMs": 12300,  "durationMs": 2000,  "words": [{"word": "It's"}, {"word": "SF"}, {"word": "dash"}, {"word": "eight"}, {"word": "eight"}, {"word": "four"}, {"word": "two"}, {"word": "seven."}]},
                    {"channel": 1, "participantPurpose": "agent",   "offsetMs": 14500,  "durationMs": 5000,  "words": [{"word": "I"}, {"word": "have"}, {"word": "your"}, {"word": "order"}, {"word": "here."}, {"word": "A"}, {"word": "sixty"}, {"word": "five"}, {"word": "inch"}, {"word": "Samsung"}, {"word": "TV."}, {"word": "I'll"}, {"word": "immediately"}, {"word": "escalate"}, {"word": "this"}, {"word": "to"}, {"word": "our"}, {"word": "damage"}, {"word": "claims"}, {"word": "team."}, {"word": "Would"}, {"word": "you"}, {"word": "prefer"}, {"word": "a"}, {"word": "replacement"}, {"word": "or"}, {"word": "a"}, {"word": "full"}, {"word": "refund?"}]},
                    {"channel": 0, "participantPurpose": "customer", "offsetMs": 19700,  "durationMs": 3000,  "words": [{"word": "I"}, {"word": "need"}, {"word": "the"}, {"word": "TV"}, {"word": "for"}, {"word": "a"}, {"word": "party"}, {"word": "this"}, {"word": "weekend."}, {"word": "Can"}, {"word": "you"}, {"word": "do"}, {"word": "an"}, {"word": "expedited"}, {"word": "replacement?"}]},
                    {"channel": 1, "participantPurpose": "agent",   "offsetMs": 22900,  "durationMs": 4500,  "words": [{"word": "I"}, {"word": "understand"}, {"word": "the"}, {"word": "urgency."}, {"word": "I"}, {"word": "can"}, {"word": "arrange"}, {"word": "an"}, {"word": "overnight"}, {"word": "replacement"}, {"word": "at"}, {"word": "no"}, {"word": "extra"}, {"word": "cost."}, {"word": "You"}, {"word": "would"}, {"word": "receive"}, {"word": "it"}, {"word": "tomorrow."}, {"word": "We"}, {"word": "will"}, {"word": "also"}, {"word": "schedule"}, {"word": "a"}, {"word": "pickup"}, {"word": "for"}, {"word": "the"}, {"word": "damaged"}, {"word": "unit."}]},
                    {"channel": 0, "participantPurpose": "customer", "offsetMs": 27600,  "durationMs": 2500,  "words": [{"word": "That's"}, {"word": "perfect."}, {"word": "I"}, {"word": "also"}, {"word": "want"}, {"word": "to"}, {"word": "leave"}, {"word": "feedback"}, {"word": "about"}, {"word": "the"}, {"word": "carrier."}, {"word": "This"}, {"word": "kind"}, {"word": "of"}, {"word": "damage"}, {"word": "is"}, {"word": "unacceptable."}]},
                    {"channel": 1, "participantPurpose": "agent",   "offsetMs": 30300,  "durationMs": 3000,  "words": [{"word": "Absolutely"}, {"word": "noted."}, {"word": "I'll"}, {"word": "include"}, {"word": "your"}, {"word": "feedback"}, {"word": "in"}, {"word": "the"}, {"word": "carrier"}, {"word": "incident"}, {"word": "report."}, {"word": "I've"}, {"word": "sent"}, {"word": "the"}, {"word": "replacement"}, {"word": "confirmation"}, {"word": "to"}, {"word": "your"}, {"word": "email."}]},
                    {"channel": 0, "participantPurpose": "customer", "offsetMs": 33500,  "durationMs": 1800,  "words": [{"word": "Thank"}, {"word": "you"}, {"word": "Alex,"}, {"word": "you've"}, {"word": "been"}, {"word": "very"}, {"word": "helpful."}]},
                    {"channel": 1, "participantPurpose": "agent",   "offsetMs": 35500,  "durationMs": 2000,  "words": [{"word": "It's"}, {"word": "my"}, {"word": "pleasure."}, {"word": "I'm"}, {"word": "sorry"}, {"word": "for"}, {"word": "the"}, {"word": "experience"}, {"word": "and"}, {"word": "enjoy"}, {"word": "your"}, {"word": "party!"}]},
                ]
            }
        ]
    },
]


def build_sample_conversations() -> List[ConversationSummary]:
    """Build ConversationSummary objects from sample transcript metadata."""
    conversations = []
    for item in SAMPLE_TRANSCRIPT_JSONS:
        meta = item["_conversation_meta"]
        start_time = datetime.fromisoformat(meta["start_time"].replace("Z", "+00:00"))
        duration_ms = meta["duration_ms"]
        end_time = datetime.fromtimestamp(
            start_time.timestamp() + duration_ms / 1000,
            tz=timezone.utc,
        )
        conversations.append(
            ConversationSummary(
                conversation_id=meta["conversation_id"],
                start_time=start_time,
                end_time=end_time,
                duration_ms=duration_ms,
                participants=[
                    {"purpose": "customer", "participant_name": "Customer"},
                    {"purpose": "agent", "participant_name": "Agent"},
                ],
                queue_id=f"queue-{meta['queue'].lower().replace(' ', '-')}",
                queue_name=meta["queue"],
            )
        )
    return conversations


def build_sample_transcripts() -> List[Transcript]:
    """Parse sample transcript JSONs into Transcript objects."""
    from gtaa.genesys.transcripts import _parse_transcript_json

    transcripts = []
    for item in SAMPLE_TRANSCRIPT_JSONS:
        meta = item["_conversation_meta"]
        # Remove the meta key before parsing
        data = {k: v for k, v in item.items() if k != "_conversation_meta"}
        transcript = _parse_transcript_json(data, meta["conversation_id"], None)
        transcripts.append(transcript)
    return transcripts
