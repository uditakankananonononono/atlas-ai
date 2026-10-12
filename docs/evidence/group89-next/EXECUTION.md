# Group 89 learned text-affect delta

Base: group88 optional isolated-worker patch after 96b4cb97. Literal group remains PARTIAL.

Added pretrained English multilabel classifier, pinned SamLowe/roberta-base-go_emotions revision d75048347613a25d77de8cf6412eaae9fa7b26be, MIT model card. Source read October 12: https://huggingface.co/SamLowe/roberta-base-go_emotions/blob/main/README.md . The model card describes 28-label Reddit GoEmotions training and reports its own evaluation. Those figures are not locally reproduced or claimed here.

Test-first: absent learned_affect import failed. Actual pinned CPU model execution labels the positive acceptance passage with joy and angry passage with anger; scores finite/range checked. Refuses empty/oversized inputs and requests to infer a real person's identity. Model invocation uses safetensors and disables remote code; oversized token inputs refuse rather than silently truncating. Local CLI executes from an input file and refuses overwriting receipts. Optional dependency group text-affect declared.

Scores are sigmoid outputs, not calibrated probabilities. This is classification of supplied text under a pretrained Reddit model, not replication of human feelings, personality, motives or intelligence. Field is only a recorded context label and does not alter the model or establish field-specific calibration. Missing context, sarcasm, demographic/training bias and domain shift remain. No human validation study, local heldout accuracy, authentic psychological simulation or clinical claims. Classifier weights download on first use; public model files only, no private text sent to an API. Existing lexicon/persona/benchmark code is not presented as learned or replaced silently.
