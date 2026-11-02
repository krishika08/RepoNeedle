"""
Check classifier generalization on Validation Set.
"""
from split import load_data
from test_intent import TestIntentClassifier

def eval_val():
    _, val_data, _ = load_data()
    print("Evaluating TestIntentClassifier on Validation Set (60 queries)...")
    y_true = []
    y_pred = []
    
    for q in val_data:
        is_gold_test_task = (q["task_type"] == "code2test")
        pred = TestIntentClassifier.classify(q["query_text"])
        y_true.append(is_gold_test_task)
        y_pred.append(pred)
        
    tp = sum(1 for yt, yp in zip(y_true, y_pred) if yt and yp)
    fp = sum(1 for yt, yp in zip(y_true, y_pred) if not yt and yp)
    fn = sum(1 for yt, yp in zip(y_true, y_pred) if yt and not yp)
    tn = sum(1 for yt, yp in zip(y_true, y_pred) if not yt and not yp)
    
    prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
    acc = (tp + tn) / len(y_true)
    
    print(f"Validation Set Classifier Metrics:")
    print(f"  Accuracy:  {acc*100:.2f}% ({tp+tn}/{len(y_true)})")
    print(f"  Precision: {prec*100:.2f}% ({tp}/{tp+fp})")
    print(f"  Recall:    {rec*100:.2f}% ({tp}/{tp+fn})")
    print(f"  F1 Score:  {f1:.4f}")
    print(f"  Confusion Matrix: TP={tp}, FP={fp}, FN={fn}, TN={tn}")

if __name__ == "__main__":
    eval_val()

