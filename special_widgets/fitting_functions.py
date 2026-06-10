import numpy as np

'''Store fitting functions used in the flex_line_plot_widget_fitting.py widget.'''
fitting_functions = {
    'Linear': {
        'params': {'m': 1e-9, 'x_0': 2.87e9},
        'function': lambda x, m, x_0: m * (x - x_0) 
    },
    'Double Lorentzian': {
        'params': {
            'A1': -0.02,
            'A2': -0.02,
            'x0': 2.868e9,
            'Δx': 6e6,
            'gamma1': 7e6,
            'gamma2': 7e6,
            'C': 1
        },
        'function': lambda x, A1, A2, x0, Δx, gamma1, gamma2, C: A1 / ((x - (x0-Δx))**2/gamma1**2+1) + A2 / ((x - (x0 + Δx))**2/gamma2**2+1) + C
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