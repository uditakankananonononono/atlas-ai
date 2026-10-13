"""Single supplied-kernel 2D cross-correlation, as used in convolution layers."""
from fractions import Fraction
import math


def extract(image,kernel,stride=1,padding='valid',activation='identity'):
    if type(stride) is not int or not 1<=stride<=4:raise ValueError('strict stride 1..4')
    if type(padding) is not str or padding not in ('valid','same'):raise ValueError('padding valid or same')
    if type(activation) is not str or activation not in ('identity','relu'):raise ValueError('activation identity or relu')
    def matrix(rows,cap):
        if type(rows) is not list or not 1<=len(rows)<=cap:raise ValueError('bounded nonempty matrix rows before scan')
        result=[];width=None
        for row in rows:
            if type(row) is not list or not 1<=len(row)<=cap:raise ValueError('bounded nonempty matrix columns before scan')
            if width is None:width=len(row)
            if len(row)!=width:raise ValueError('rectangular matrix required')
            values=[]
            for value in row:
                if type(value) not in (int,float) or not -1000<=value<=1000 or not math.isfinite(value):
                    raise ValueError('strict finite bounded image/kernel value')
                values.append(Fraction(str(value)))
            result.append(values)
        return result
    img=matrix(image,32);filt=matrix(kernel,5)
    h,w=len(img),len(img[0]);kh,kw=len(filt),len(filt[0])
    if padding=='valid':
        if kh>h or kw>w:raise ValueError('valid kernel must fit image')
        oh=(h-kh)//stride+1;ow=(w-kw)//stride+1;top=left=0
    else:
        oh=(h+stride-1)//stride;ow=(w+stride-1)//stride
        top=max(0,(oh-1)*stride+kh-h)//2;left=max(0,(ow-1)*stride+kw-w)//2
    output=[]
    for r in range(oh):
        line=[]
        for c in range(ow):
            total=Fraction(0)
            for a in range(kh):
                for b in range(kw):
                    y=r*stride+a-top;x=c*stride+b-left
                    if 0<=y<h and 0<=x<w:total+=img[y][x]*filt[a][b]
            if activation=='relu':total=max(Fraction(0),total)
            line.append(str(total))
        output.append(line)
    return {'features_fraction':output,'shape':[oh,ow],'padding_top_left':[top,left],
            'stride':stride,'padding':padding,'activation':activation,
            'operation':'cross-correlation, kernel not flipped; zero padding with odd excess on bottom/right',
            'units':'image units times supplied kernel units',
            'kernel_learning_performed':False,'semantic_features_verified':False,
            'network_training_performed':False,'external_effects':[]}
