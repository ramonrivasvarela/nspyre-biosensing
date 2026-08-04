###########################
# imports
###########################

# std
import os
import pickle
import time

import importlib
from nspyre import InstrumentManager, DataSource
import numpy as np

# nspyre
from nspyre import StreamingList
from nspyre import experiment_widget_process_queue, nspyre_init_logger
import logging
from pathlib import Path



try:
    # nspyre has had a few historical locations for this
    _plotting = importlib.import_module('nspyre.gui.widgets.plotting')  # type: ignore[reportMissingImports]
    LinePlotWidget = getattr(_plotting, 'LinePlotWidget')
except Exception:  # pragma: no cover
    try:
        _line_plot = importlib.import_module('nspyre.gui.widgets.line_plot')  # type: ignore[reportMissingImports]
        LinePlotWidget = getattr(_line_plot, 'LinePlotWidget')
    except Exception:  # pragma: no cover
        LinePlotWidget = object

# base WF helpers
from experiments.wfExperiment import WFSpyrelet
_HERE = Path(__file__).parent
_logger = logging.getLogger(__name__)
###########################
# classes
###########################

class wODMRSpyrelet(WFSpyrelet):
    def __init__(self, queue_to_exp=None, queue_from_exp=None):
        """
        Args:
            queue_to_exp: A multiprocessing Queue object used to send messages
                to the experiment from the GUI.
            queue_from_exp: A multiprocessing Queue object used to send messages
                to the GUI from the experiment.
        """
        self.queue_to_exp = queue_to_exp
        self.queue_from_exp = queue_from_exp

    def __enter__(self):
        """Perform experiment setup."""
        # config logging messages
        # if running a method from the GUI, it will be run in a new process
        # this logging call is necessary in order to separate log messages
        # originating in the GUI from those in the new experiment subprocess
        nspyre_init_logger(
            log_level=logging.INFO,
            log_path=_HERE / '../logs',
            log_path_level=logging.DEBUG,
            prefix=Path(__file__).stem,
            file_size=10_000_000,
        )
        _logger.info('Created Experiment instance.')


    def __exit__(self):
        """Perform experiment teardown."""
        _logger.info('Destroyed Experiment instance.')

    #### INIT HELPER FUNCTIONS ###############################################################################################
    ## Param Setting Functions (set variables)
    def set_label_self_params(self, label, alt_label):
        t = 't' # Needed to parse apart 't' (throwaway) pulses in input
        self.label = eval(label)
        self.label_inv = []
        if alt_label:
            for pulse in self.label:
                if pulse == 1:
                    self.label_inv.append(0)
                elif pulse == 0:
                    self.label_inv.append(1)
                elif pulse == 't':
                    self.label_inv.append('t')
        self.full_label = self.label+ self.label_inv
        self.full_label_filtered = [pulse for pulse in self.full_label if pulse != 't']
        return
        
    ## Initialization Functions (set up devices and more complex variables)
    def init_sg(self, mgr, rf_amplitude, mode):
        mgr.sg.set_rf_toggle(False)
        mgr.sg.set_rf_amplitude(rf_amplitude)
        if mode == 'QAM':
            mgr.sg.set_mod_type('QAM')
            mgr.sg.set_mod_function('QAM', 'external')
        elif mode == 'AM':
            mgr.sg.set_mod_type('AM')
            mgr.sg.set_AM_mod_depth(100)
            mgr.sg.set_mod_function('AM', 'external')
        mgr.sg.set_mod_toggle(True)
        return

    def init_seq(self, mgr, alt_label, mode, uw_duty, uw_rep): 
        self.main_seq=mgr.Pulser.WF_prep_ODMR(self.label, self.exp_time, self.readout_time, trig = self.trigger_time, buff = self.buffer_time, mode = mode, uw_duty = uw_duty, uw_rep = uw_rep, dim_throwaway = self.Misc.get('dim_throwaway', True)) 
        if alt_label:

            self.alt_seq=mgr.Pulser.WF_prep_ODMR(self.label_inv, self.exp_time, self.readout_time, trig = self.trigger_time, buff = self.buffer_time, mode = mode, uw_duty = uw_duty, uw_rep = uw_rep, dim_throwaway = self.Misc.get('dim_throwaway', True))
        self.n_gain = 2                                      #(Hardcoded) | number of pulses in gain sequence, should be at least 2 to get a sense of dynamics
        self.gain_seq=mgr.Pulser.WF_prep_gain_seq(self.n_gain,self.exp_time, self.readout_time, trig = self.trigger_time, buff = self.buffer_time)
        return
    ###########################################################################################################################
    def initialize(self, mgr, exp_time, readout_time, sweeps, label, frequencies, gain, gain_setting, cooler, cam_trigger, rf_amplitude, uw_duty, uw_rep, mode, ROI_xy, alt_label, alt_sleep_time, trackpy_params, focus_bool,
                   data_path, save_image, data_download, shutdown, window_params, verbose, Misc):
        
        print('Initializing ODMR')
        
        #### General Param Formatting: ###############################################
        ## Runtime
        self.t0 = time.time()
        self.Misc = eval(Misc)  # Must always be initialized as one of first variables, since other variables can check Misc for overrides. Any self.Misc.get('var', default) is a 
                                # hardcoded value that can be overridden by the user through the Misc dict in the params.
        self.verbose = verbose
        self.debug = self.Misc.get('DEBUG', False)
        ## Camera Timings
        self.set_pulse_self_params(exp_time, readout_time, self.Misc.get('trigger_time', 0.010), self.Misc.get('buffer_time', 0.005)) # self.exp_time | self.readout_time | self.trigger_time | self.buffer_time | self.pulse_len
        ## Windowing
        self.set_windowing_self_params(window_params) # self.window_interval | self.ct_for_window | self.window | self.all_ROI | self.r_display
        ## NDs
        self.set_ND_self_params(mgr, ROI_xy, self.Misc.get('r_track', 10), self.Misc.get('r_targ', 7)) #  self.ND_List | self.r_track | self.r_targ | self.z_pos
        ## Labelling
        self.set_label_self_params(label, alt_label) # self.label | self.label_inv | self.full_label
        ## Timeout
        self.set_timeout_param() # self.timeout_limit
        ## Routine
        freqs = np.linspace(eval(frequencies)[0], eval(frequencies)[1], eval(frequencies)[2], endpoint = True)
        self.sg_freqs = freqs
        ## Trackpy 
        self.trackpy_params = eval(trackpy_params)
        #### SG init ########################################################################
        self.init_sg(mgr, rf_amplitude, mode) # init signal generator
        #### Cam init ########################################################################
        self.init_camera(mgr, cam_trigger) # camera initialized and ready to acquire
        #### Seq init ########################################################################
        self.init_seq(mgr, alt_label, mode, uw_duty, uw_rep) # self.main_seq | self.alt_seq (if alt_label) | self.gain_seq | sequences initialized and ready to acquire
        #### Experiment Specific Init #####################################################################
        #### Cooldown if necessary ########################################################################
        do_cool, temp = eval(cooler)
        if do_cool:
            self.cool_loop(mgr, temp)
        #### Checks for validity ################################################
        # Dependent on protocol
        #### Data formatting, pickle prep ###############################################
        self.init_data_saving(data_path, data_download, save_image) # self.data_path | self.latest_imgs

        print('Initialization finished')
    
    #### MAIN HELPER FUNCTIONS ###############################################################################################
    ## Initialization Functions (set up devices and more complex variables) and Param Setting Functions
    def init_main_loop(self, mgr, mode):
        ## Prepare camera
        mgr.Camera.set_number_kinetics(len(self.label))
        ## Prepare SG, ps
        Q_set = -1 if mode == 'AM' else 0 # ODMR ONLY
        mgr.Pulser.set_state([6], Q_set, 0.0) #set pulser to safe output
        mgr.sg.set_rf_toggle(True)
        return
    ## Analysis Functions (data formatting, analysis)
    def analyze_sig(self, data): # TEMPLATE
        '''
        Analyzes acquired data by pooling all signal (1) and background (0) into a single value-per-ND,
        as well as a list of output-per-ND. Note redundancy of information - can technically move this
        analysis to the plotting software. Probably worth it for the new NSpyre. 
        '''
        # dependent on process. Roughly this will consist of:
        # Define for each sig a list, by ND, and allowing for multiple entries due to multiple runs.
        sig = [[] for _ in self.ND_iter]
        bg = [[] for _ in self.ND_iter]
        # Define sig all of the signals for this run, for all NDs, to be added to the acquisition dict regardless of protocol, for maximum flexibility in post-processing.
        sig_all = [[] for _ in self.ND_iter] # For collecting all signals.
        if self.debug:
            print('DEBUG IN PROGRESS... CHECKING ANALYSIS WITH T PULSES')
            lbl = self.full_label
        else:
            lbl = self.full_label_filtered
        # begin processing images:
        for i in range(len(data)):
            extracted_sig = self.img_to_sig(self.ND_list, data[i], r_ROI = self.r_targ) #array of [ND] signals from a given image.
            for ND in self.ND_iter: sig_all[ND].append(int(extracted_sig[ND]))
            if lbl[i] == 1:
                for ND in self.ND_iter: sig[ND].append(int(extracted_sig[ND]))
            elif lbl[i] == 0:
                for ND in self.ND_iter: bg[ND].append(int(extracted_sig[ND]))
            else:
                print('throwaway pulse, ignoring...')
        ls_sig = [int(np.mean(sig[ND])) for ND in range(len(self.ND_list))]
        ls_bg = [int(np.mean(bg[ND])) for ND in range(len(self.ND_list))]
        output = {'sig': ls_sig, 'bg': ls_bg, 'sig_all': sig_all}
        return output
    ###########################################################################################################################
    def main(self, exp_time, readout_time, sweeps, label, frequencies, gain, gain_setting, cooler, cam_trigger, rf_amplitude, uw_duty, uw_rep, mode, ROI_xy, alt_label, alt_sleep_time, trackpy_params, focus_bool,
                   data_path, save_image, data_download, shutdown, window_params, verbose, dataset, Misc):
        
        params={"exp_time": exp_time, "readout_time": readout_time, "sweeps": sweeps, "label": label, "frequencies": frequencies, "gain": gain, "gain_setting": gain_setting, "cooler": cooler, "cam_trigger": cam_trigger, "rf_amplitude": rf_amplitude, "uw_duty": uw_duty, "uw_rep": uw_rep, "mode": mode, "ROI_xy": ROI_xy, "alt_label": alt_label, "alt_sleep_time": alt_sleep_time, "trackpy_params": trackpy_params, "focus_bool": focus_bool, "data_path": data_path, "save_image": save_image, "data_download": data_download, "shutdown": shutdown, "verbose": verbose, "window_params": window_params,  "Misc": Misc}
        with InstrumentManager() as mgr, DataSource(dataset) as data_source:
            self.initialize(mgr, exp_time, readout_time, sweeps, label, frequencies, gain, gain_setting, cooler, cam_trigger, rf_amplitude, uw_duty, int(uw_rep), mode, ROI_xy,
                           alt_label,
                           alt_sleep_time,
                           trackpy_params,
                           focus_bool,
                           data_path,
                           save_image,
                           data_download,
                           shutdown,
                           window_params,
                           verbose,
                           Misc)
            representative_img = None # useful for saving and windowing, a running representative image.
            #### Optimize gain/ take images to reset camera dynamics #################################################
            self.gain, max_value, representative_img = self.init_gain(
                mgr,
                gain,
                gain_setting,
                self.Misc.get('ideal_pixel_range', (2.1e4,2.9e4)),
                self.Misc.get('max_checks', 20),
                self.Misc.get('max_gain', 140),
                self.Misc.get('gain_wait_time', 0.5),
                self.Misc.get('img_cycles_no_gain_optimization', 2),
                save=save_image,
            ) # runs self.acquire several times.
            print(f'gain: {self.gain}, giving max pixel value of roughly {max_value}')

            #### Trackpy #################################################################################################################
            n_bg_pts = self.init_ND_list(mgr, representative_img) # self.ND_list | self.ND_iter | some print statements | runs trackpy if necessary to find NDs.

            #### Begin Experiment ################################################################################################################
            try: # I hope there's a better way to do this. Asking Evan and Omri - 7/13/26
                self.init_main_loop(mgr, mode) # Any experiment-specific initialization before main loop, such as defining sequences, running initial sequences, etc.
                data_dict={}
                for ND in range(len(self.ND_list)): 
                    data_dict[f'signal_{ND}'] = StreamingList() # initialize empty streaming list for each ND to be added to acquisition dict
                    data_dict[f'background_{ND}'] = StreamingList()
                    data_dict[f'signal_all_{ND}'] = StreamingList()
                data_dict['z_pos'] = StreamingList() # for tracking z position during experiment, to be added to acquisition dict
                # if self.window:
                #     WindowList=StreamingList()
                n_freqs = len(self.sg_freqs)
                time_initial= time.time()
                for sweep in range(sweeps):
                    ## main loop ################################################################################################################
                    self.unsaved_imgs = {} # dict to hold unsaved images for this sweep, key is img name, value is img to save.
                    sig_counts=np.empty(n_freqs)
                    sig_counts[:]=np.nan
                    
                    bg_counts=np.empty(n_freqs)
                    bg_counts[:]=np.nan
                    sig_all_counts=np.empty(n_freqs)
                    sig_all_counts[:]=np.nan
                    for i in range(len(self.ND_list)):
                        data_dict[f'signal_{i}'].append(np.stack([self.sg_freqs, sig_counts]))
                        data_dict[f'background_{i}'].append(np.stack([self.sg_freqs, bg_counts]))
                        data_dict[f'signal_all_{i}'].append(np.stack([self.sg_freqs, sig_all_counts]))
                    for i, f_hz in enumerate(self.sg_freqs):
                        if verbose: print("frequency: ", f_hz)
            
                        mgr.sg.set_frequency(f_hz)
                        if self.Misc.get('pdb', False): import pdb; pdb.set_trace()
                        if alt_label:
                            data_1D = self.GetPic_Alternating(mgr, self.main_seq, self.alt_seq, len(self.label), alt_sleep_time, saving=save_image) # Get data as list of 1D arrays, alternating between two labels
                        else:
                            data_1D = self.GetPic(mgr, self.main_seq, len(self.label), saving=save_image) 
                            # Get data as list of 1D arrays, saving any images during wait if all images are to be saved
                        # Go through the new data and format it. Add it to unsaved imgs.
                        current_time = time.time()
                        data = []

                        for j, img_1D in enumerate(data_1D):
                            if self.full_label[j] != 't' or self.debug:
                                img = self.img_1D_to_2D(img_1D, 1024, 1024)
                                data.append(img)
                                if save_image in ['raw_images', 'raw_images_safe']:
                                    im_name = f'image_s{sweep+1}_f{i}_{j}'
                                    self.unsaved_imgs[im_name] = img
                                if save_image == 'raw_images_safe':
                                    self.save_pics()
                            elif self.debug:
                                print('DEBUG, ADDING IN T PULSE IMAGES FOR ANALYSIS. CHECKING THAT THEY ARE NOT BEING MISTAKEN FOR REAL SIGNALS.')
                                img = self.img_1D_to_2D(img_1D, 1024, 1024)
                                data.append(img)

                        ## Track NDs
                        self.ND_list, _ = self.track_NDs(self.ND_list, data[-1], r_search=self.r_track, number_bg_pts=n_bg_pts)

                        ## ANALYSIS
                        output_dict = self.analyze_sig(data)
                        for ND in range(len(self.ND_list)):
                            data_dict[f'signal_{ND}'][-1][1][i] = output_dict['sig'][ND]
                            data_dict[f'signal_{ND}'].updated_item(-1)
                            data_dict[f'background_{ND}'][-1][1][i] = output_dict['bg'][ND]
                            data_dict[f'background_{ND}'].updated_item(-1)
                            # data_dict[f'signal_all_{ND}'][-1][1][i] = output_dict['sig_all'][ND]
                            # data_dict[f'signal_all_{ND}'].updated_item(-1)
                        data_dict[f'z_pos'].append(np.array([np.array([current_time-time_initial]),np.array([self.z_pos])]))
                        data_dict[f'z_pos'].updated_item(-1)

                        
                        

                        ## Acquire.
                        # dependent on process. Example of an acquisition dict.


                        if self.window:
                            # WindowList.append(np.array([np.array([time.time()-self.t0]),np.array([ls_mx])]))
                            data_dict['window'] = self.format_windows(mgr, data[-1], focus_bool=focus_bool)[0]
                            px_x = self.ND_list[0][0]
                            px_y = self.ND_list[0][1]
                            xs = np.asarray(range(px_x-self.r_display, px_x+self.r_display))
                            ys = np.asarray(range(px_y-self.r_display, px_y+self.r_display))
                        else:
                            xs = np.asarray(range(0, 1))
                            ys = np.asarray(range(0, 1))

                        acq_dict = {
                            'params': params,
                            'xlabel': 'frequency (Hz)',
                            'ylabel': 'counts (/s)',
                            'datasets': data_dict,
                            'output': { 'number_ND':len(self.ND_iter), 
                                        'frequencies': self.sg_freqs, 
                                        'current_sweep': sweep,
                            },
                            'xs': xs,
                            'ys': ys
                        }
                        
                        
                        data_source.push(acq_dict) # push acquisition dict to data source, which will handle saving and plotting. Note that the data source is separate from the experiment, and can be used across different experiments for consistent saving and plotting.
                        if experiment_widget_process_queue(self.queue_to_exp) == 'stop':
                            # the GUI has asked us nicely to exit
                            self.finalize(mgr,exp_time, readout_time, sweeps, frequencies, gain, rf_amplitude, ROI_xy, alt_label, data_download, shutdown)
                            return
                    ###########################################################################
                    representative_img = img
                    self.save_after_sweep(img, save_image, sweep)
                    print(f'Finished sweep {sweep+1}/{sweeps}, time elapsed: {time.time() - self.t0} seconds.')
                    
                self.finalize(mgr,exp_time, readout_time, sweeps, frequencies, gain, rf_amplitude, ROI_xy, alt_label, data_download, shutdown)
                return
            except:
                time.sleep(1)
                self.finalize(mgr,exp_time, readout_time, sweeps, frequencies, gain, rf_amplitude, ROI_xy, alt_label, data_download, shutdown)
                raise
        

    #### FINALIZE HELPER FUNCTIONS ###############################################################################################
    def save_config(self, data_download, sweeps, alt_label, rf_amplitude, frequencies, gain, exp_time, readout_time, ROI_xy):
        total_time = time.time() - self.t0
        if data_download:
            config = {'VERSION': 2, 'label': self.label, 'gain': self.gain, 'sweeps': sweeps, 'alt_label': alt_label, 'rf': rf_amplitude,'NDs_input': eval(ROI_xy),
                      'NDs': self.ND_list, 'n_ND': len(self.ND_list), 'freqs': frequencies, 'exp_time': exp_time, 'readout_time': readout_time, 'total_time': total_time} 
            os.mkdir(self.data_path+'\\data')
            with open(self.data_path+f'\\data\\config.pkl', 'wb') as file: 
                pickle.dump(config, file)
            with open(self.data_path+f'\\data\\config.txt', "w") as file:
                file.write(str(config))
        return total_time
    ###########################################################################################################################
    def finalize(self, mgr,exp_time, readout_time, sweeps, frequencies, gain, rf_amplitude, ROI_xy, alt_label, data_download, shutdown): 
        #### SG off ###############################################################################################
        self.finalize_sg(mgr)
        #### Cam close ###############################################################################################
        self.finalize_camera(mgr, shutdown)
        #### Additional Analysis ###############################################################################################
        # Ex. Quasilinear slope extraction, fitting, etc.
        #### Data saving ###############################################################################################
        total_time = self.save_config(data_download, sweeps, alt_label, rf_amplitude, frequencies, gain, exp_time, readout_time, ROI_xy)
        #### Final Print Statements ###############################################################################################
        first_10_ROI = self.ND_list[:10]
        print(f'The updated ND locations: {first_10_ROI}... ({len(first_10_ROI)} of {len(self.ND_list)} shown)')
        print(f"Finalizing finished, total time: {total_time} seconds")
        return



    # @PlotFormatInit(LinePlotWidget, ['ODMR_div'])
    # def init_format(p):
    #     p.xlabel = 'frequency (Hz)'
    #     p.ylabel = 'PL (cts)'

    # @Plot2D
    # def window(df, cache):
    #     ND = 0
    #     try:
    #         latest_image = df['window'].dropna().iloc[-1][ND]
    #     except KeyError:
    #         latest_image = np.zeros((1024,1024))
    #     return latest_image

    # @Plot1D
    # def ODMR_div(df, cache):
    #     ND = 0
    #     grouped = df.groupby('f')
    #     sigs = grouped['sig'] #also returns  groupby object, still with 'f' as the index, but with only sigs associated. A list of sigs (which is itself a list)
    #     bgs = grouped['bg']
    #     sigs_averaged = sigs.apply(list).apply(lambda val_set: [vals_by_ND[ND] for vals_by_ND in val_set]).apply(np.mean)
    #     bgs_averaged = bgs.apply(list).apply(lambda val_set: [vals_by_ND[ND] for vals_by_ND in val_set]).apply(np.mean)
    #     return {'ODMR': [sigs_averaged.index, sigs_averaged/bgs_averaged]}

    # @Plot1D
    # def raw_signals(df, cache):
    #     ND = 0
    #     try:
    #         grouped = df.groupby('f')
    #         sigs = grouped['sig'] #also returns  groupby object, still with 'f' as the index, but with only sigs associated. A list of sigs (which is itself a list)
    #         bgs = grouped['bg']
    #         sigs_averaged = sigs.apply(list).apply(lambda val_set: [vals_by_ND[ND] for vals_by_ND in val_set]).apply(np.mean)
    #         bgs_averaged = bgs.apply(list).apply(lambda val_set: [vals_by_ND[ND] for vals_by_ND in val_set]).apply(np.mean)
    #         return {'sig': [sigs_averaged.index, sigs_averaged],
    #                 'bg': [bgs_averaged.index, bgs_averaged]}
    #     except KeyError:
    #         return
        
    # @Plot1D
    # def latest_signals(df, cache):
    #     ND = 0
    #     try:
    #         df = df[df.sweep_idx == df.sweep_idx.max()] # filter for latest sweep
    #         grouped = df.groupby('f')
    #         sigs = grouped['sig'] #also returns  groupby object, still with 'f' as the index, but with only sigs associated. A list of sigs (which is itself a list)
    #         bgs = grouped['bg']
    #         sigs_averaged = sigs.apply(list).apply(lambda val_set: [vals_by_ND[ND] for vals_by_ND in val_set]).apply(np.mean)
    #         bgs_averaged = bgs.apply(list).apply(lambda val_set: [vals_by_ND[ND] for vals_by_ND in val_set]).apply(np.mean)
    #         return {'sig': [sigs_averaged.index, sigs_averaged],
    #                 'bg': [bgs_averaged.index, bgs_averaged]}
    #     except KeyError:
    #         return
        
    # @Plot1D
    # def z_position(df, cache):
    #     ND = 0
    #     try: 
    #         df_clean = df.dropna(subset = ['time', 'z_pos'])
    #         z_pos = df_clean['z_pos'].tolist()
    #         time = df_clean['time'].tolist()
    #         return {'z_pos': [time, z_pos]}
    #     except KeyError:
    #         return
    
    # @Plot1D
    # def acquisition_fluorescence(df, cache):
    #     ND = 0
    #     tail = 50

    #     df = df.dropna(subset = ['sig_all'])
    #     df_tail = df.tail(tail)
    #     normalized_dt_raw = [np.array(row[ND]) for row in df_tail['sig_all'].values]
    #     normalized_dt_raw_arr = np.stack(normalized_dt_raw)
    #     mean_normalized = np.mean(normalized_dt_raw_arr, axis=0)
    #     return {'raw': [list(range(len(mean_normalized))),mean_normalized],}
        
