"""Build next-token or single-position masked-token labels from input sequences.

Mask collision validation runs in both modes: next_token also refuses any input
token equal to the mask token, even though its output does not insert a mask.
"""


def build(sequences,mode,mask_token='[MASK]'):
    if type(mode) is not str or mode not in ('next_token','masked_token'):
        raise ValueError('mode must be next_token or masked_token')
    if type(mask_token) is not str or not 1<=len(mask_token)<=120 or not mask_token.strip():
        raise ValueError('bounded nonblank mask token')
    if type(sequences) is not list or not 1<=len(sequences)<=100:
        raise ValueError('1..100 sequences before scan')
    for sequence in sequences:
        if type(sequence) is not list or not 2<=len(sequence)<=100:
            raise ValueError('2..100 tokens per sequence before scan')
        for token in sequence:
            if type(token) is not str or not 1<=len(token)<=120 or not token.strip():
                raise ValueError('bounded nonblank string token')
            if token==mask_token:raise ValueError('mask token must not occur in inputs')
    examples=[]
    for sequence_id,sequence in enumerate(sequences):
        positions=range(1,len(sequence)) if mode=='next_token' else range(len(sequence))
        for position in positions:
            if mode=='next_token':context=sequence[:position]
            else:
                context=list(sequence);context[position]=mask_token
            examples.append({'sequence_index':sequence_id,'label_position':position,
                             'input_tokens':context,'label':sequence[position]})
    return {'mode':mode,'examples':examples,'example_count':len(examples),
            'label_source':'original input token at declared position',
            'model_training_performed':False,'semantic_label_truth_verified':False,
            'split_independence_verified':False,'external_effects':[],
            'split_requirement':'split original sequences before generating examples; source sequence indices are preserved',
            'assumptions':['caller supplied tokenization','generated labels reconstruct tokens, not external semantic truth']}
