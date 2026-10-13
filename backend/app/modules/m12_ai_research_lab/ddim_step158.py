"""Deterministic eta-zero DDIM step on supplied scalar-channel image/noise grids.

The caller provides noise predictions; no denoiser or high-quality-image claim.
"""
import math


def step(noisy_image,predicted_noise,alpha_current,alpha_previous):
    for value in (alpha_current,alpha_previous):
        if type(value) not in (int,float) or not .000001<=value<=1 or not math.isfinite(value):
            raise ValueError('strict finite cumulative alpha within 1e-6..1')
    if alpha_previous<alpha_current:raise ValueError('previous cumulative alpha must be at least current')
    def grid(rows):
        if type(rows) is not list or not 1<=len(rows)<=32:raise ValueError('1..32 image rows before scan')
        result=[];width=None
        for row in rows:
            if type(row) is not list or not 1<=len(row)<=32:raise ValueError('1..32 image columns before scan')
            if width is None:width=len(row)
            if len(row)!=width:raise ValueError('rectangular image required')
            for value in row:
                if type(value) not in (int,float) or not -1000<=value<=1000 or not math.isfinite(value):
                    raise ValueError('strict finite grid value within -1000..1000')
            result.append(list(row))
        return result
    image=grid(noisy_image);noise=grid(predicted_noise)
    if len(image)!=len(noise) or len(image[0])!=len(noise[0]):raise ValueError('identical image/noise shape required')
    clean=[];previous=[]
    for row,eps in zip(image,noise):
        x0=[(x-math.sqrt(1-alpha_current)*e)/math.sqrt(alpha_current) for x,e in zip(row,eps)]
        xp=[math.sqrt(alpha_previous)*x+math.sqrt(1-alpha_previous)*e for x,e in zip(x0,eps)]
        clean.append(x0);previous.append(xp)
    return {'predicted_clean_image':clean,'previous_image':previous,'eta':0,
            'alpha_current':alpha_current,'alpha_previous':alpha_previous,
            'units':'same scalar-channel image units; supplied noise in same normalized convention',
            'clipping_performed':False,'denoiser_execution_performed':False,
            'high_quality_image_verified':False,'trained_diffusion_model_used':False,
            'external_effects':[],
            'assumptions':['supplied noise predictions use epsilon parameterization',
                           'alphas are cumulative products, not per-step beta or alpha',
                           'deterministic eta-zero DDIM; no stochastic variance term']}
