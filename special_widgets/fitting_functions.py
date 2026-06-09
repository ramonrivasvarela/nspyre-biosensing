import numpy as np

'''Store fitting functions used in the flex_line_plot_widget_fitting.py widget.'''
fitting_functions = {
    'Linear': {
        'params': {'m': 1e-9, 'x_0': 2.87e9},
        'function': lambda x, m, x_0: m * (x - x_0) + 1
    },
    'Double Lorentzian': {
        'params': {
            'A1': -0.2,
            'A2': -0.2,
            'x_1': 2.865e9,
            'x_2': 2.875e9,
            'gamma1': 1e6,
            'gamma2': 1e6,
            'C': 1
        },
        'function': lambda x, A1, A2, x_1, x_2, gamma1, gamma2, C: A1 / ((x - x_1)**2/gamma1**2+1) + A2 / ((x - x_2)**2/gamma2**2+1) + C
    },
    'Exponential Decay': {
        'params': {
            'A': 1,
            'tau': 1,
            'C': 0
        },
        'function': lambda x, A, tau, C: A * np.exp(-x / tau) + C
    },
}