import numpy as np
from enum import Enum
import six


class OutputState():
    """class that defines an output state of Pulse Streamer 8/2"""
    digital_channel=8
    analog_channel=2
    analog_range=1
    analog_conv=0x7fff
    conv_type=int

    def __init__(self, digi, A0=0.0, A1=0.0):
        #set analog values
        assert (abs(A0)<=OutputState.analog_range and abs(A1)<=OutputState.analog_range), "Pulse Streamer 8/2 supports "\
                "analog voltage range of +/-"+str(OutputState.analog_range) +"V" #check hardware
        self.__A0=OutputState.conv_type(round(OutputState.analog_conv*A0))
        self.__A1=OutputState.conv_type(round(OutputState.analog_conv*A1))

        ##set obligatory argument for digital channels
        if isinstance(digi, list):        
            self.__digi=self.chans_to_mask(digi)
        else:
            raise TypeError("digi has to be a list with elements of type int")        

    def getData(self):
        """return data in specific format"""
        #collect return values in list, start with obligatory digital value
        return(self.__digi, self.__A0, self.__A1)
        
    def chans_to_mask(self, chans):
        """convert channel list into bitmask"""
        mask = 0
        for chan in chans:
            assert chan in range(OutputState.digital_channel),"Pulse Streamer 8/2 supports "\
            "up to " +str(OutputState.digital_channel)+ " digital channels"
            mask |= 1<<chan
        return mask

    @staticmethod
    def ZERO():
        """Static method to create an OutputState object for the Pulse Streamer 8/2 which sets all outputs to 0"""
        return OutputState([],)


class Sequence():

    digital_channel=8
    analog_channel=2
    analog_range=1
    analog_conv=0x7fff
    conv_type=int
    pulse_dtype = np.dtype([('count','<u4'), ('digi','<u1'), ('a0','<i2'),('a1','<i2')])
    #max_seq_step=2e6 #currently not used

    def __init__(self, pulser=None):
        self.__union_seq=np.array(np.zeros(1), dtype=self.pulse_dtype)
        self.__sequence_up_to_date = True
        self.__duration =0
        self.__all_t_cumsums_concatinated=np.array([], dtype=np.int64)
        self.__pad_seq=dict.fromkeys(range (Sequence.digital_channel+Sequence.analog_channel), (np.array([0], dtype=np.int64), np.array([0], dtype=np.float64), np.array([0], dtype=np.int64)))
        self.__channel_digital= dict.fromkeys(range(Sequence.digital_channel), (np.array([0], dtype=np.int64), np.array([0], dtype=np.int64), np.array([0], dtype=np.int64)))
        self.__channel_analog=dict.fromkeys(range(Sequence.analog_channel), (np.array([0], dtype=np.int64), np.array([0], dtype=np.float64), np.array([0], dtype=np.int64)))
        self.__channel_digital_return=dict.fromkeys(range(Sequence.digital_channel), ([(0, 0)], np.array([0], dtype=np.int64)))
        self.__channel_analog_return=dict.fromkeys(range(Sequence.analog_channel), ([(0, 0.0)], np.array([0], dtype=np.int64)))
        self.__pad_seq_return=dict.fromkeys(range(Sequence.digital_channel + Sequence.analog_channel), None)

    def __union(self):
        """Merges all channels to final list of sequence-steps"""
        # idea of the algorithm
        # 1) for each channel, get the absolute timestamps (not the relative) -> t_cumsums stored in self.__pad_seq[x][2]
        # 2) join all these absolute timestamps together to a sorted unique list. This results in the timestamps (unique_t_cumsum) of the final pulse list 
        # 3) expand every single channel to the final pulse list (unique_t_cumsum)
        # 4) join the channels together
        # 5) Simplify Sequence by concatenating states with the same digital and analog values

        #get channel numbers - currently just use the class atrributes
        count_digital_channels = Sequence.digital_channel
        count_analog_channels = Sequence.analog_channel
        count_all_channels = count_digital_channels + count_analog_channels
        
        # 1) Done in setDigital/setAnalog functions
        # 2) join all these absolute timestamps together to a sorted unique list. This results in the timestamps (unique_t_cumsum) of the final pulse list
        self.__pad()
        unique_t_cumsum = np.unique(self.__all_t_cumsums_concatinated)

        # 3) expand every single channel to the final pulse list (unique_t_cumsum)
        # create 2d array for every channel and timestamp
        data = np.zeros([count_all_channels, len(unique_t_cumsum)], dtype=np.float64)
        
        for i in range(count_all_channels):
            #get channel data and cumsum of current channel
            cumsum = self.__pad_seq[i][2]
            np_array = self.__pad_seq[i][1]
            data[i] = np_array[np.searchsorted(cumsum, unique_t_cumsum, side='left')]

        # 4) join the channels together
        #digital channels
        if count_digital_channels != 0:
            digi = np.int_(data[0,:])
        else:
            digi = np.zeros(len(unique_t_cumsum))

        for i in range(1, count_digital_channels):
            digi = digi + np.int_((2**i)*data[i,:])
        #analog channels
        ana=[]
        for i in range(count_analog_channels):
            ana.append((np.round(data[count_digital_channels + i]*Sequence.analog_conv)).astype(Sequence.conv_type))

        #5) Simplify Sequence by concatenating states with the same digital and analog values
        if len(digi)>1:
            #get indexes of equal digital values in a row
            redundant = digi[:-1]==digi[1:]
            for a in ana:
                redundant &= a[:-1]==a[1:]
            index = np.nonzero(redundant)

            #delete the elements (absolute timestamps, digital and analog values)
            unique_t_cumsum = np.delete(unique_t_cumsum,index)
            digi = np.delete(digi,index)
            ana =[np.delete(a,index) for a in ana]

        # revert the cumsum to get the relative pulse durations
        ts = np.insert(np.diff(unique_t_cumsum), 0, unique_t_cumsum[0])
        
        #split pulses with countvalue > 32bit
        if (ts > 0xffffffff).any():
            div, mod = np.divmod(ts, ts.size*[0xffffffff])
            index = np.nonzero(div)
            ts_c = [] 
            digi_c = []
            a0_c = []
            a1_c = []
            last=0
            for i in index[0]:
                ts_c+=ts[last:i].tolist()
                digi_c+=digi[last:i].tolist()
                a0_c+=ana[0][last:i].tolist()
                a1_c+=ana[1][last:i].tolist()
                ts_c.extend(div[i]*[0xffffffff])
                digi_c.extend(div[i]*[digi[i]])
                a0_c.extend(div[i]*[ana[0][i]])
                a1_c.extend(div[i]*[ana[1][i]])
                if(mod[i]!=0):
                    ts_c.append(mod[i])
                    digi_c.append(digi[i])
                    a0_c.append(ana[0][i])
                    a1_c.append(ana[1][i])
                last=i+1
            
            ts_c+=ts[last:].tolist()
            digi_c+=digi[last:].tolist()
            a0_c+=ana[0][last:].tolist()
            a1_c+=ana[1][last:].tolist()
    
            ts=np.array(ts_c)
            digi=np.array(digi_c)
            ana[0]=np.array(a0_c)
            ana[1]=np.array(a1_c)
        
        #create structurred numpy array
        result=np.zeros(ts.size, dtype=self.pulse_dtype)
        result['count']=ts
        result['digi']=digi
        result['a0']=ana[0]
        result['a1']=ana[1]
        
        # there might be a pulse duration of 0 in the very beginning - remove it
        if len(result) > 1:
            if result[0][0] == 0:
                return result[1::]
        
        return result

    def __pad(self):
        """Pad all channels to the maximal channel duration"""
        #get the max duration of all channels
        duration = np.int64(self.getDuration())
        #pad each digital channel with last value and store padded sequence data in dict for digital and analog channels
        for key, pattern_data in self.__channel_digital.items():
            pad_value=duration-pattern_data[2][-1]
            pad_level=pattern_data[1][-1]
            if (pad_value!=0):
                if (duration==pad_value):
                    #channel has only been initialized
                    self.__pad_seq[key]=(np.array([pad_value]), np.array([pad_level]), np.array([duration], dtype=np.int64))
                else:
                    #pad with last value and update cumulated timestamps
                    self.__pad_seq[key]=(np.append(pattern_data[0], pad_value), np.append(pattern_data[1], pad_level), np.append(pattern_data[2], duration))
            else:
                #channel data is already complete
                self.__pad_seq[key]=pattern_data

        #pad each analog channel with last value and store padded sequence data in dict for digital and analog channels
        for key, pattern_data in self.__channel_analog.items():
            pad_value=duration-pattern_data[2][-1]
            pad_level=pattern_data[1][-1] 
            if (pad_value!=0):
                if (duration==pad_value):
                    #channel has only been initialized
                    self.__pad_seq[key+Sequence.digital_channel] = (np.array([pad_value]), np.array([pad_level]), np.array([duration], dtype=np.int64))
                else:
                    #pad with last value and update cumulated timestamps
                    self.__pad_seq[key+Sequence.digital_channel] = (np.append(pattern_data[0], pad_value), np.append(pattern_data[1], pad_level), np.append(pattern_data[2], duration))
            else:
                #channel data is already complete
                self.__pad_seq[key+Sequence.digital_channel]=pattern_data

        # make an array with all padded cumsums
        self.__all_t_cumsums_concatinated=np.array([], dtype=np.int64)
        for key in self.__pad_seq:
            self.__all_t_cumsums_concatinated = np.append(self.__all_t_cumsums_concatinated, self.__pad_seq[key][2])


    def get_pad(self, as_ndarray=False):
        """returns padded Sequence and cumsum"""
        if not self.__sequence_up_to_date:
            self.__pad()
        if as_ndarray:
            #get data as a tuple of np.ndarrays - internal use only
            for i in range(Sequence.digital_channel + Sequence.analog_channel):
                self.__pad_seq_return[i]=(self.__pad_seq[i][0], self.__pad_seq[i][1], self.__pad_seq[i][2])
        else:
            for i in range(Sequence.digital_channel + Sequence.analog_channel):
                self.__pad_seq_return[i]=(list(zip(self.__pad_seq[i][0], self.__pad_seq[i][1])), self.__pad_seq[i][2])

        return self.__pad_seq_return

    def setDigital(self, channel, channel_sequence):
        """set one or a list of digital channels"""
        if not isinstance(channel, list):
            channel = [channel]
        #channel number check
        for i in channel:
            assert i in range(Sequence.digital_channel), "Pulse Streamer 8/2 supports "\
            "up to " +str(Sequence.digital_channel)+ " digital "\
            "and " +str(Sequence.analog_channel)+ " analog channels"
        #set control flag that sequence has to be unified again before returned
        self.__sequence_up_to_date = False
        
        if isinstance(channel_sequence, list):            
            #create arrays for timeline and channel states
            timeline=np.array([t for t,p in channel_sequence], dtype=np.int64)
            ch_state=np.array([p for t,p in channel_sequence], dtype=np.int64)
        else:
            #set channel with nd.arrays - internal use only
            timeline=channel_sequence[0]
            ch_state=channel_sequence[1]
            assert isinstance(timeline, np.ndarray), "channel_sequence has to be of type list or a tuple of two  instances of type np.ndarray"
            assert isinstance(ch_state, np.ndarray), "channel_sequence has to be of type list or a tuple of two  instances of type np.ndarray"
            assert timeline.size == ch_state.size, "Error: Both np.ndarrays must be of same size"
        if timeline.size > 0:
            #delete all zeros except for the last value
            zeros=np.where(timeline[:-1] == 0)
            timeline=np.delete(timeline, zeros)
            ch_state=np.delete(ch_state, zeros)
            ### argument range check 
            assert ch_state.all() in [0,1], "Digital values must either be 0 or 1"
            assert timeline.all() >=0, "time value <0"
            # make a numeric array of the cumulated timestamps
            cumsum=np.cumsum(timeline)
        else:
            cumsum = np.array([0], dtype=np.int64)
            timeline= np.array([0], dtype=np.int64)
            ch_state= np.array([0], dtype=np.int64)

        #Store data and cumulated timestamps
        for i in channel:
            self.__channel_digital[i]= (timeline, ch_state, cumsum)

    def getDigital(self, as_ndarray=False):
        """returns digital channels data as an array of tuples"""
        if as_ndarray:
            #get data as a tuple of np.ndarrays - internal use only
            for i in range(Sequence.digital_channel):
                self.__channel_digital_return[i]=(self.__channel_digital[i][0], self.__channel_digital[i][1], self.__channel_digital[i][2])
        else:
            for i in range(Sequence.digital_channel):
                self.__channel_digital_return[i]=(list(zip(self.__channel_digital[i][0], self.__channel_digital[i][1])), self.__channel_digital[i][2])

        return self.__channel_digital_return

    def invertDigital(self, channel):
        """invert one or a list of digital channels"""
        if not isinstance(channel, list):
            channel = [channel]
        #channel number check
        for i in channel:
            assert i in range(Sequence.digital_channel), "Pulse Streamer 8/2 supports "\
            "up to " +str(Sequence.digital_channel)+ " digital "\
            "and " +str(Sequence.analog_channel)+ " analog channels"
        #set control flag that sequence has to be unified again before returned
        self.__sequence_up_to_date = False
        
        #invert channels
        for i in channel:
            self.__channel_digital[i]=(self.__channel_digital[i][0], self.__channel_digital[i][1]^1, self.__channel_digital[i][2])

    def setAnalog(self, channel, channel_sequence):
        """set one or a list of analog channels"""
        if not isinstance(channel, list):
            channel = [channel]
        for i in channel:
            assert i in range(Sequence.analog_channel), "Pulse Streamer 8/2 supports "\
            "up to " +str(Sequence.digital_channel)+ " digital "\
            "and " +str(Sequence.analog_channel)+ " analog channels"
        #set control flag that sequence has to be unified again before returned
        self.__sequence_up_to_date = False

        if isinstance(channel_sequence, list):
            #create arrays for timeline and channel values
            timeline=np.array([t for t,p in channel_sequence], dtype=np.int64)
            ch_value=np.array([p for t,p in channel_sequence], dtype=np.float64)
        else:
            #set channel with nd.arrays - internal use only
            timeline=channel_sequence[0]
            ch_value=channel_sequence[1]
            assert isinstance(timeline, np.ndarray), "channel_sequence has to be of type list or a tuple of two  instances of type np.ndarray"
            assert isinstance(ch_value, np.ndarray), "channel_sequence has to be of type list or a tuple of two  instances of type np.ndarray"
            assert timeline.size == ch_value.size, "Error: Both np.ndarrays must be of same size"
        if timeline.size > 0:
            #delete all zeros except for the last value
            zeros=np.where(timeline[:-1] == 0)
            timeline=np.delete(timeline, zeros)
            ch_value=np.delete(ch_value, zeros)
            ### argument range check
            assert np.abs(ch_value).all() <= Sequence.analog_range, "Pulse Streamer 8/2 supports "\
                "analog voltage range of +/-"+str(Sequence.analog_range) +"V"
            assert timeline.all()>=0, "time value <0"
            # make a numeric array of the cumulated timestamps
            cumsum=np.cumsum(timeline)
        else:
            cumsum = np.array([0], dtype=np.int64)
            timeline= np.array([0], dtype=np.int64)
            ch_value= np.array([0], dtype=np.float64)

        for i in channel:
            self.__channel_analog[i] = (timeline, ch_value, cumsum)
	
    def getAnalog(self, as_ndarray=False):
        """returns analog channels data as an array of tuples"""
        if as_ndarray:
            #get data as a tuple of np.ndarrays - internal use only
            for i in range(Sequence.analog_channel):
                self.__channel_analog_return[i]=(self.__channel_analog[i][0], self.__channel_analog[i][1], self.__channel_analog[i][2])
        else:
            for i in range(Sequence.analog_channel):
                self.__channel_analog_return[i]=(list(zip(self.__channel_analog[i][0], self.__channel_analog[i][1])), self.__channel_analog[i][2])

        return self.__channel_analog_return

    def invertAnalog(self, channel):
        """invert one or a list of analog channels"""
        if not isinstance(channel, list):
            channel = [channel]
        for i in channel:
            assert i in range(Sequence.analog_channel), "Pulse Streamer 8/2 supports "\
            "up to " +str(Sequence.digital_channel)+ " digital "\
            "and " +str(Sequence.analog_channel)+ " analog channels"
        #set control flag that sequence has to be unified again before returned
        self.__sequence_up_to_date = False

        #invert channels
        for i in channel:
            self.__channel_analog[i]=(self.__channel_analog[i][0], self.__channel_analog[i][1]*(-1), self.__channel_analog[i][2])

    def getData(self, as_ndarray=False):
        """returns final list of sequence steps"""
        #check if sequence has to be rebuild
        if not self.__sequence_up_to_date:
            #merge all channels over final unified timestamps
            self.__union_seq = self.__union()
            #set flag that final data has been build
            self.__sequence_up_to_date = True
        
        if as_ndarray==True:
            return self.__union_seq
        else:
            return self.__union_seq.tolist()

    def isEmpty(self):
        """returns True if no channel has been set"""
        #check digital channels
        for key, pattern_data in self.__channel_digital.items():
            if pattern_data[2][-1] != 0:
                return False
            else:
                pass
        #check analog channels
        for key, pattern_data in self.__channel_analog.items():
            if pattern_data[2][-1] != 0:
                return False
            else:
                pass

        return True

    def getDuration(self):
        """returns duration of sequence (ns)"""
        duration =0
        for key, pattern_data in self.__channel_digital.items():
            channel_duration = pattern_data[2][-1]
            duration = max(duration, channel_duration)

        for key, pattern_data in self.__channel_analog.items():
            channel_duration = pattern_data[2][-1]
            duration = max(duration, channel_duration)
        
        return duration

    def getLastState(self):
        """returns last sequence step as OutputState object"""
        ana={}
        digi=[]
        #check if sequence has to be padded
        if not self.__sequence_up_to_date:
            self.__pad()
        for key, pattern_data in self.__pad_seq.items():
            if key < Sequence.digital_channel:
                if (pattern_data[1][-1]):
                    #save digital values if set
                    digi.append(key)
            else:
                #save analog values
                ana.update({'A'+str(key-Sequence.digital_channel):pattern_data[1][-1]})
                
        #create and return OutputState object
        return OutputState(digi, ana['A0'], ana['A1'])

    @staticmethod
    def concatenate(seq1, seq2):
        """returns sequence object as a Concatenation of two sequences """
        #get padded data of left side
        pad= seq1.get_pad(as_ndarray=True)
        #get data of right side
        digital_2 = seq2.getDigital(as_ndarray=True)
        analog_2 = seq2.getAnalog(as_ndarray=True)
        #create new Sequence
        ret=seq1.__class__()
        for key, pattern in pad.items():
            if key > (Sequence.digital_channel-1):
                #set analog channels of new Sequence
                if np.count_nonzero(analog_2[key-Sequence.digital_channel][0]) > 0:
                    #channel was set in seq1 and seq2 => concatenate and remember (used_list)
                    ret.setAnalog(key-Sequence.digital_channel, (np.append(pattern[0], analog_2[key-Sequence.digital_channel][0]), np.append(pattern[1], analog_2[key-Sequence.digital_channel][1])))
                else:
                    #channel was only used in seq1
                    ret.setAnalog((key-Sequence.digital_channel), (pattern[0], pattern[1]))
            else:
                #set digital channels of new sequence
                if np.count_nonzero(digital_2[key][0]) > 0:
                    #channel was set in seq1 and seq2 => concatenate and remember (used_list)
                    ret.setDigital(key, (np.append(pattern[0], digital_2[key][0]), np.append(pattern[1], digital_2[key][1])))
                else:
                    #channel was only used in seq1
                    ret.setDigital(key, (pattern[0], pattern[1]))

        return ret

    def __add__(self, another):
        """Overriding __add__  to make concatenate() also working with seq3=seq1+seq2"""
        return Sequence.concatenate(self, another)


    @staticmethod
    def repeat(seq, n_times):
        """returns sequence object as n_times repetition of seq"""
        #get padded sequence data
        pad= seq.get_pad(as_ndarray=True)
        #create new sequence
        ret=seq.__class__()
        #set channels with repeated channel data
        for key in pad:
            if key > (Sequence.digital_channel-1):
                ret.setAnalog(key-Sequence.digital_channel, (np.tile(pad[key][0], n_times), np.tile(pad[key][1], n_times)))
            else:             
                ret.setDigital(key,(np.tile(pad[key][0], n_times), np.tile(pad[key][1], n_times)))
        
        return ret
    
    def __mul__(self, other):
        """Overrideing __mul__ to make sure repeat() also works with seq2=seq1*x"""
        return Sequence.repeat(self, other)

    def __rmul__(self,other):
        """Overrideing __rmul__ to make sure repeat() also works with seq2=x*seq1"""
        return Sequence.repeat(self, other)
    
    def __re_zoom_in_plot(self, event):
        """Little helper function for zooming in plots generated by matplotlib"""
        zoom = 1.0
        shift=0
        update=False
        #get the change in scale of axes that have changed scale
        for ax in event.canvas.figure.axes:
            current_xlim = ax.get_xlim()
            old_xlim = ax.old_xlim
            if old_xlim != current_xlim:
                zoom = (current_xlim[1]-current_xlim[0])/(old_xlim[1]-old_xlim[0])
                shift = (current_xlim[1]-old_xlim[1] + current_xlim[0]-old_xlim[0])/2.0
                update=True

        #return if all axes need no update
        if not update:
            return
        # change the scale of axes that need an update
        for ax in event.canvas.figure.axes: 
            current_xlim = ax.get_xlim()
            old_xlim = ax.old_xlim
            if old_xlim == current_xlim:
                mid = shift+(old_xlim[0] + old_xlim[1])/2.0
                dif = zoom*(old_xlim[1] - old_xlim[0])/2.0
                current_xlim = (mid - dif, mid + dif)
                ax.set_xlim(*current_xlim)
            ax.old_xlim = current_xlim
        # re-draw the canvas (if required)
        if zoom != 1.0 or shift!=0:
            event.canvas.draw()             
    
    def plot(self):
        """plots sequence data using matplotlib"""
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            print("Module matplotlib not found.")
            print("For visualizing the sequence data via Sequence().plot(), please manually install the package by typing: ")
            print("> pip install matplotlib")
            print("in your terminal.")
            return
        self.__pad()

        fig = plt.figure()
        for key, pattern_data in self.__pad_seq.items():
            #create timeline to plot - add 0 to cumsum
            t=np.concatenate((np.array([0], dtype=np.int64), pattern_data[2]))
            #create channel data for plotting - with last element
            plot_ch_data= np.append(pattern_data[1], pattern_data[1][-1])

            ax=plt.subplot(10,1, (10-key))
            
            if key >0:
                plt.setp(ax.get_xticklabels(), visible=False)
            else:
                plt.xlabel("time/ns")
            if key>(Sequence.digital_channel-1):
                plt.ylabel("A"+str(key-Sequence.digital_channel), labelpad=20, rotation='horizontal')
                plt.setp(ax.get_yticklabels(), fontsize=6)
                plt.ylim(-1.5, 1.5)
                plt.box(on=None)
            else:
                plt.ylabel("D"+str(key), labelpad=20, rotation='horizontal')
                plt.setp(ax.get_yticklabels(), fontsize=6)
                plt.ylim(0,1.5)
                plt.box(on=None)
            plt.step(t, plot_ch_data, ".-",  where='post', color='k')
            
            ax.old_xlim = ax.get_xlim()  # store old values so changes can be detected

        plt.tight_layout(pad=0.5)
        fig.canvas.manager.set_window_title('Sequence')
        plt.connect('motion_notify_event', self.__re_zoom_in_plot)  # for right-click pan/zoom
        plt.connect('button_release_event', self.__re_zoom_in_plot) # for rectangle-select zoom
        plt.show()


