"""Monotone posterior inference with the released three-state dynamics."""
import numpy as np
from scipy.optimize import brentq
from scipy.special import expit, logsumexp
from scipy.sparse import csr_matrix


class MonotoneChain:
    def __init__(self, model, coarse):
        self.lag = model['lag']
        self.regimes = model['transition']
        self.prior = model['regime_prior']
        self.count = len(self.prior)
        self.width = len(self.lag)
        self.zero = self.width//2
        self.shifts = model['shifts']
        step = self.lag[1]-self.lag[0]
        self.cutoff = np.maximum(self.shifts[0],np.floor(-np.diff(coarse)/step+1.e-9).astype(int)+1)
        self.operators = {}
        for cut in np.unique(self.cutoff):
            origin, dest, weight = [],[],[]
            for regime,kernel in enumerate(model['step_kernel']):
                for col,d in enumerate(self.shifts):
                    if d<cut:
                        continue
                    indices = np.arange(max(0,-d),min(self.width,self.width-d))
                    v = kernel[indices,col]
                    valid = v>0
                    origin.extend(regime*self.width+indices[valid])
                    dest.extend(regime*self.width+indices[valid]+d)
                    weight.extend(v[valid])
            size = self.count*self.width
            forward = csr_matrix((weight,(dest,origin)),shape=(size,size))
            self.operators[cut] = (forward,forward.T.tocsr())

    def posterior(self, evidence):
        length = len(evidence)
        alphas = np.empty((length,self.count,self.width),dtype='f')
        a = np.zeros((self.count,self.width))
        a[:,self.zero] = self.prior
        alphas[0] = a
        logz = 0.
        for i in range(1,length):
            predicted = self.operators[self.cutoff[i-1]][0] @ (self.regimes.T @ a).ravel()
            a = predicted.reshape(self.count,self.width)*evidence[i]
            normalizer = a.sum()
            if normalizer<=0 or not np.isfinite(normalizer):
                raise ValueError(f'No monotone path at row {i}')
            a /= normalizer
            alphas[i] = a
            logz += np.log(normalizer)
        b = np.ones_like(a)
        marginals = np.empty((length,self.width))
        for i in range(length-1,-1,-1):
            marginal = (alphas[i]*b).sum(axis=0)
            marginals[i] = marginal/marginal.sum()
            if i:
                pull = self.operators[self.cutoff[i-1]][1] @ (b*evidence[i]).ravel()
                b = self.regimes @ pull.reshape(self.count,self.width)
                b /= b.max()
        return marginals,logz


def infer(model, coarse, logits, null, maximum_steps):
    chain = MonotoneChain(model,coarse)
    lag = model['lag']
    logits = np.array(logits,dtype=float,copy=True)
    # Use the nominal support of the categorical acoustic training problem.
    no_candidates = ~np.isfinite(np.max(logits,axis=1))
    logits[no_candidates] = 0
    norm = logsumexp(logits,axis=1)
    odds = np.clip(norm-null,-32.,32.)
    odds[no_candidates] = -32.
    match = len(lag)*np.exp(logits-norm[:,None])
    valid = ((coarse[:,None]+lag>=coarse[0]) & (coarse[:,None]+lag<=coarse[-1]))
    valid[[0,-1]]=False
    valid[[0,-1],len(lag)//2]=True
    bias = 0.
    trace = []
    first = None
    for iteration in range(maximum_steps+1):
        reliability = expit(odds+bias)
        signal = reliability[:,None]*match
        emission = signal+(1-reliability[:,None])
        observed = emission * valid
        observed[[0,-1]] = valid[[0,-1]]
        marginal,logz = chain.posterior(observed)
        # Endpoints are supplied conditions, not acoustic training examples.
        expected_match = ((signal/emission)*marginal).sum(axis=1)
        inner = slice(1,-1)
        trace.append(dict(iteration=iteration,bias=float(bias),log_evidence=float(logz),
                          expected_match=float(np.mean(expected_match[inner]))))
        if first is None:
            first = marginal,expected_match,logz
        # Maximise the expected Bernoulli log likelihood with a unit normal intercept prior.
        goal = expected_match[inner].sum()
        f = lambda b: expit(odds[inner]+b).sum()+b-goal
        next_bias = brentq(f,-65.,65.)
        if iteration and logz-.5*bias**2 < trace[-2]['log_evidence']-.5*trace[-2]['bias']**2-1e-5:
            raise RuntimeError('EM decreased its penalized marginal likelihood')
        if abs(next_bias-bias)<1e-3 or iteration==maximum_steps:
            break
        bias = next_bias
    # BIC charges one fitted recording-level parameter; the common baseline is bias=0.
    accept = 2*(logz-.5*bias**2-first[2])>np.log(len(coarse))
    if not accept:
        marginal,expected_match,_ = first
    return marginal,expected_match,trace,bool(accept)
