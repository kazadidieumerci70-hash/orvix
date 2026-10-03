import unittest
from types import SimpleNamespace
from app.retrieval import rank_scores, retrieval_query


class RetrievalTests(unittest.TestCase):
    def test_accents_and_case_do_not_hide_a_match(self):
        scores = rank_scores(['La filtration du néphron.', 'La digestion.'], 'NEPHRON')
        self.assertGreater(scores[0], scores[1])

    def test_whole_words_avoid_false_matches(self):
        scores = rank_scores(['Le portrait est bleu.', 'Le port maritime.'], 'port')
        self.assertEqual(scores[0], 0)
        self.assertGreater(scores[1], 0)

    def test_followup_reuses_user_topic_not_assistant_claim(self):
        history = [SimpleNamespace(role='user', content='Explique la filtration du néphron'),
                   SimpleNamespace(role='assistant', content='INVENTED_TOPIC')]
        query = retrieval_query('Donne un exemple', history)
        self.assertIn('néphron', query)
        self.assertNotIn('INVENTED_TOPIC', query)

    def test_new_detailed_question_does_not_reuse_old_topic(self):
        message = 'Décris les étapes principales de la photosynthèse végétale'
        self.assertEqual(retrieval_query(message, [SimpleNamespace(role='user', content='néphron')]), message)

    def test_reference_and_confusion_keep_latest_topic_only(self):
        history = [SimpleNamespace(role='user', content='Explique le néphron'), SimpleNamespace(role='user', content='Explique la photosynthèse')]
        for message in ['Pourquoi ?', 'Je n’ai pas compris la deuxième partie', 'Et dans ce cas ?', 'Plus simple', 'En bref']:
            query = retrieval_query(message, history)
            self.assertIn('photosynthèse', query)
            self.assertNotIn('néphron', query)

    def test_explicit_subject_overrides_followup_word(self):
        message = 'Explique encore la photosynthèse'
        self.assertEqual(retrieval_query(message, [SimpleNamespace(role='user', content='néphron')]), message)


if __name__ == '__main__':
    unittest.main()
