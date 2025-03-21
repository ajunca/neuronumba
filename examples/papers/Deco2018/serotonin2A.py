# ==========================================================================
# ==========================================================================
# Dynamic Mean Field (DMF) model (a.k.a., Reduced Wong-Wang), from
#
# [Deco_2018] G. Deco, A. Ponce-Alvarez, P. Hagmann, G.L. Romani, D. Mantini, M. Corbetta
#             How local excitation-inhibition ratio impacts the whole brain dynamics
#             J. Neurosci., 34 (2018), pp. 7886-7898
# ==========================================================================
import numpy as np
import numba as nb
from overrides import overrides

from neuronumba.basic.attr import Attr
from neuronumba.fitting.fic.fic import FICHerzog2022
from neuronumba.numba_tools.addr import address_as_void_pointer
from neuronumba.numba_tools.types import NDA_f8_2d
from neuronumba.simulator.models import Model
from neuronumba.simulator.models import LinearCouplingModel


class Deco2018(LinearCouplingModel):
    # Se, excitatory synaptic activity
    state_vars = Model._build_var_dict(['S_e', 'S_i'])
    n_state_vars = len(state_vars)
    c_vars = [0]

    # Ie, excitatory current
    # re, excitatory firing rate
    observable_vars = Model._build_var_dict(['Ie', 're'])
    n_observable_vars = len(observable_vars)

    auto_fic = Attr(default=False, attributes=Model.Type.Model)
    taon = Attr(default=100.0, attributes=Model.Type.Model)
    taog = Attr(default=10.0, attributes=Model.Type.Model)
    gamma_e = Attr(default=0.641, attributes=Model.Type.Model)
    gamma_i = Attr(default=1.0, attributes=Model.Type.Model)
    I0 = Attr(default=0.382, attributes=Model.Type.Model)     # [nA] overall effective external input
    w = Attr(default=1.4, attributes=Model.Type.Model)
    J_NMDA = Attr(default=0.15, attributes=Model.Type.Model)  # [nA] NMDA current
    Jext_e = Attr(default=1.0, attributes=Model.Type.Model)
    Jext_i = Attr(default=0.7, attributes=Model.Type.Model)
    ae = Attr(default=310.0, attributes=Model.Type.Model)
    be = Attr(default=125.0, attributes=Model.Type.Model)
    de = Attr(default=0.16, attributes=Model.Type.Model)
    ai = Attr(default=615.0, attributes=Model.Type.Model)
    bi = Attr(default=177.0, attributes=Model.Type.Model)
    di = Attr(default=0.087, attributes=Model.Type.Model)
    J = Attr(default=1.0, attributes=Model.Type.Model)
    I_external = Attr(default=0.0, attributes=Model.Type.Model)

    receptor = Attr(default=0.0, attributes=Model.Type.Model)
    w_gain_e = Attr(default=0.0, attributes=Model.Type.Model)
    w_gain_i = Attr(default=0.0, attributes=Model.Type.Model)

    @overrides
    def _init_dependant(self):
        super()._init_dependant()
        if self.auto_fic and not self._attr_defined('J'):
            self.J = FICHerzog2022().compute_J(self.weights, self.g)

    @property
    def get_state_vars(self):
        return Deco2018.state_vars

    @property
    def get_observablevars(self):
        return Deco2018.observable_vars

    @property
    def get_c_vars(self):
        return Deco2018.c_vars

    def initial_state(self, n_rois):
        state = np.empty((Deco2018.n_state_vars, n_rois))
        state[0] = 0.001
        state[1] = 0.001
        return state

    def initial_observed(self, n_rois):
        observed = np.empty((Deco2018.n_observable_vars, n_rois))
        observed[0] = 0.0
        observed[1] = 0.0
        return observed

    def get_numba_dfun(self):
        m = self.m.copy()
        P = self.P

        @nb.njit(nb.types.UniTuple(nb.f8[:, :], 2)(nb.f8[:, :], nb.f8[:, :]))
        def Deco2018_dfun(state: NDA_f8_2d, coupling: NDA_f8_2d):
            # Clamping, needed in Deco2018 model and derivatives...
            Se = state[0, :].clip(0.0,1.0)
            Si = state[1, :].clip(0.0,1.0)

            # Eq for I^E (5). I_external = 0 => resting state condition.
            Ie = m[np.intp(P.Jext_e)] * m[np.intp(P.I0)] + m[np.intp(P.w)] * m[np.intp(P.J_NMDA)] * Se + m[np.intp(P.J_NMDA)] * coupling[0, :] - m[np.intp(P.J)] * Si + m[np.intp(P.I_external)]
            # Eq for I^I (6). \lambda = 0 => no long-range feedforward inhibition (FFI)
            Ii = m[np.intp(P.Jext_i)] * m[np.intp(P.I0)] + m[np.intp(P.J_NMDA)] * Se - Si
            y = (m[np.intp(P.ae)] * Ie - m[np.intp(P.be)]) * (1.0 + m[np.intp(P.receptor)]*m[np.intp(P.w_gain_e)])
            # In the paper re was g_E * (I^{(E)_n} - I^{(E)_{thr}}). In the paper (7)
            # Here, we distribute as g_E * I^{(E)_n} - g_E * I^{(E)_{thr}}, thus...
            re = y / (1.0 - np.exp(-m[np.intp(P.de)] * y))
            y = (m[np.intp(P.ai)] * Ii - m[np.intp(P.bi)]) * (1.0 + m[np.intp(P.receptor)]*m[np.intp(P.w_gain_i)])
            # In the paper ri was g_I * (I^{(I)_n} - I^{(I)_{thr}}). In the paper (8)
            # Apply same distributing as above...
            ri = y / (1.0 - np.exp(-m[np.intp(P.di)] * y))
            # divide by 1000 because we need milliseconds!
            dSe = -Se / m[np.intp(P.taon)] + m[np.intp(P.gamma_e)] * (1. - Se) * re / 1000.
            dSi = -Si / m[np.intp(P.taog)] + m[np.intp(P.gamma_i)] * ri / 1000.
            return np.stack((dSe, dSi)), np.stack((Ie, re))

        return Deco2018_dfun
