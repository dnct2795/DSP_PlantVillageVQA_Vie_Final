# Sao chép từ pvvqa/evaluation/generate.py + pvvqa/data/collator.prompt_messages (repo model của Khoa).
# Khác biệt: đồng bộ cả MPS lẫn CUDA khi đo thời gian.
import copy
import time

import torch

_UNUSED_SAMPLING_FLAGS = ('temperature', 'top_p', 'top_k')


def prompt_messages(sample, system_prompt):
    return [dict(role='system', content=[dict(type='text', text=system_prompt)]),
            dict(role='user', content=[dict(type='image', image=sample['image']),
                                      dict(type='text', text=sample['question'])])]


def synchronize(device):
    if device.type == 'cuda':
        torch.cuda.synchronize()
    elif device.type == 'mps':
        torch.mps.synchronize()


def greedy_generation_config(model, max_new_tokens, num_beams):
    source = getattr(model, 'generation_config', None)
    if source is None:
        return None
    config = copy.deepcopy(source)
    config.do_sample = False
    config.num_beams = num_beams
    config.max_new_tokens = max_new_tokens
    for name in _UNUSED_SAMPLING_FLAGS:
        if hasattr(config, name):
            setattr(config, name, None)
    return config


@torch.inference_mode()
def generate_answer(model, processor, image, question, system_prompt, max_new_tokens=64, do_sample=False, num_beams=1,
                    stopping_criteria=None, use_cache=None):
    model.eval()
    messages = prompt_messages(dict(image=image, question=question), system_prompt)
    inputs = processor.apply_chat_template(messages, tokenize=True, add_generation_prompt=True,
                                           return_dict=True, return_tensors='pt')
    device = next(model.parameters()).device
    inputs = {k: v.to(device) if hasattr(v, 'to') else v for k, v in inputs.items()}
    synchronize(device)
    start = time.perf_counter()
    generate_kwargs = dict(do_sample=do_sample, num_beams=num_beams, max_new_tokens=max_new_tokens)
    if stopping_criteria is not None:
        generate_kwargs['stopping_criteria'] = stopping_criteria
    if use_cache is not None:
        generate_kwargs['use_cache'] = use_cache
    if not do_sample:
        config = greedy_generation_config(model, max_new_tokens, num_beams)
        if config is not None:
            generate_kwargs['generation_config'] = config
    output = model.generate(**inputs, **generate_kwargs)
    synchronize(device)
    elapsed = time.perf_counter() - start
    text = processor.batch_decode(output[:, inputs['input_ids'].shape[1]:], skip_special_tokens=True,
                                  clean_up_tokenization_spaces=False)[0].strip()
    return dict(answer=text, latency_seconds=elapsed)
