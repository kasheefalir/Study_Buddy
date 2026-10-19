from scripts.evaluate_quiz_overlap import candidate_problem


def draft(question, answer, others):
    return {"question": question, "correct_answer": answer, "options": [answer, *others]}


def test_distinguishing_subject_is_not_a_stem_echo():
    assert not candidate_problem(draft(
        "Which set supplies the mean and standard deviation?",
        "The training set mean and standard deviation",
        ["The test set mean and standard deviation", "The validation set statistics", "The entire dataset statistics"]))


def test_generic_words_and_negation_cannot_rescue_echo():
    assert candidate_problem(draft(
        "What is the purpose of using the left-arrow symbol for variable assignment in R?",
        "The left-arrow symbol is used for variable assignment in R.",
        ["It opens help.", "It prints a plot.", "It adds a package."]))
    assert candidate_problem(draft(
        "What effect does adding an extreme observation to a dataset typically have on its median?",
        "Have no effect on the median",
        ["Increase the median", "Decrease the median", "Increase or decrease the median"]))


def test_repeated_options_still_rejected():
    assert candidate_problem(draft("Which set supplies statistics?", "Training", ["Training", "Test", "Validation"]))


def test_distinctive_word_is_not_evidence_of_correctness():
    # A reason to keep this candidate offline: validation is distinctive but
    # is the wrong source of statistics for the held-out test transformation.
    assert not candidate_problem(draft(
        "When standardizing a held-out test set, which of the following should be used for mean and standard deviation?",
        "The mean and standard deviation of the validation set",
        ["The mean and standard deviation of the test set",
         "The mean and standard deviation of the training set",
         "The mean and standard deviation of the entire dataset"]))
