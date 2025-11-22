# evaluation/rag_eval.py
from assistant import ask_assistant
from retrieval_eval import TEST_CASES, queries, awards
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import faithfulness, answer_correctness
import json

print("Running full RAG evaluation (takes ~2 minutes)...")
answers = [ask_assistant(q, a) for q, a in zip(queries, awards)]

dataset = Dataset.from_dict({
    "question": queries,
    "answer": answers,
    "contexts": [[] for _ in answers],
    "ground_truth": ["Accurate list of award-winning ReadyTensor projects"] * len(answers)
})

result = evaluate(dataset, metrics=[faithfulness, answer_correctness])
print("\nFull RAG Results:")
print(result)

with open("outputs/rag_eval_results.json", "w") as f:
    json.dump(result.to_dict(), f, indent=2)
