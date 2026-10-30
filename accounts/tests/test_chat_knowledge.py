import json
from pathlib import Path

from django.contrib.auth.models import User
from django.test import TestCase

from accounts.models import CourseResult, Profile
from accounts.views import _chatbot_answer, _load_chat_knowledge, _match_chat_intents


QUESTION_CASES_PATH = Path(__file__).with_name("chat_question_cases.json")


class ChatKnowledgeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user = User.objects.create_user(
            username="knowledge-student",
            email="knowledge-student@example.com",
            password="NotARealPassword123!",
        )
        cls.student = Profile.objects.create(
            user=user,
            role=Profile.Role.STUDENT,
            department="B.Sc. Computer Science",
        )
        mentor_user = User.objects.create_user(
            username="knowledge-mentor",
            first_name="Knowledge",
            last_name="Mentor",
            password="knowledge-test-password",
        )
        cls.mentor = Profile.objects.create(
            user=mentor_user,
            role=Profile.Role.STAFF,
            department="B.Sc. Computer Science",
        )
        cls.student.mentor = cls.mentor
        cls.student.save(update_fields=("mentor",))
        CourseResult.objects.create(
            subject="Computer Science",
            pass_percentage=75,
            published_by=user,
        )

    def test_sample_question_matrix_matches_expected_intents(self):
        cases = json.loads(QUESTION_CASES_PATH.read_text(encoding="utf-8"))
        knowledge = _load_chat_knowledge()
        self.assertGreaterEqual(len(cases), 15)
        for case in cases:
            with self.subTest(question=case["question"]):
                matched = [
                    intent["id"]
                    for intent in _match_chat_intents(case["question"], knowledge)
                ]
                self.assertEqual(matched, case["expected_intents"])
                response = _chatbot_answer(case["question"], self.student)
                for expected_text in case["expected_answer_contains"]:
                    self.assertIn(expected_text, response["answer"])

    def test_fee_aliases_use_the_editable_knowledge_file(self):
        response = _chatbot_answer("How much is tuition?", self.student)
        self.assertIn("Term fee: 10,000", response["answer"])
        self.assertIn("Total: 35,000", response["answer"])
        self.assertFalse(response["needs_mentor"])

    def test_multi_part_question_gets_each_supported_topic(self):
        response = _chatbot_answer(
            "What is the fee structure and which course is offered?",
            self.student,
        )
        self.assertIn("Current fee structure:", response["answer"])
        self.assertIn("B.Sc. Computer Science", response["answer"])
        self.assertFalse(response["needs_mentor"])

    def test_unknown_and_unconfigured_schedule_questions_abstain(self):
        unknown = _chatbot_answer("What time does the library close?", self.student)
        schedule = _chatbot_answer("When does the timetable start?", self.student)
        self.assertTrue(unknown["needs_mentor"])
        self.assertTrue(schedule["needs_mentor"])
        self.assertIn("I don't have reliable information", unknown["answer"])
        self.assertIn("I don't have reliable information", schedule["answer"])
        self.assertGreaterEqual(len(unknown["suggestions"]), 1)

    def test_similar_typing_is_fuzzy_matched_without_matching_unrelated_words(self):
        self.assertEqual(
            [intent["id"] for intent in _match_chat_intents("What is the tuiton cost?")],
            ["fees"],
        )
        self.assertEqual(_match_chat_intents("Tell me about my favorite hobby"), [])
