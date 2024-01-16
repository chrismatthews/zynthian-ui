#pragma once

#include <string>
#include <jack/jack.h> //provides interface to JACK
#include <sndfile.h> //provides sound file manipulation
#include <jack/ringbuffer.h> //provides jack ring buffer
#include <samplerate.h> //provides samplerate conversion
#include <rubberband/RubberBandStretcher.h> //provides rubberband time/freq warp

class AUDIO_PLAYER; // Have to declare audio player class to allow typdef to work that uses the class...

typedef void cb_fn_t(void*, AUDIO_PLAYER*, int, float);

enum playState {
    STOPPED		= 0,
    STARTING	= 1,
    PLAYING		= 2,
    STOPPING	= 3
};

enum seekState {
    IDLE,       // Not seeking
    SEEKING,    // Seeking within file
    LOADING,    // Seek complete, loading data from file
    LOOPING,    // Reached loop end point, need to load from loop start point
    WAITING     // File buffer is full so wait a cycle then try again
};

enum fileState {
    FILE_CLOSED,
    FILE_OPENING,
    FILE_OPEN
};

enum envState {
    ENV_IDLE = 0,
    ENV_ATTACK,
    ENV_DECAY,
    ENV_SUSTAIN,
    ENV_RELEASE,
    ENV_END
};

class AUDIO_PLAYER {

    public:
    jack_port_t* jack_out_a;
    jack_port_t* jack_out_b;
    uint32_t index; // A number to identify each player (jack ports)

    uint8_t file_open = FILE_CLOSED;; // 0=file closed, 1=file opening, 2=file open - used to flag thread to close file or thread to flag file failed to open
    uint8_t file_read_status = IDLE; // File reading status (IDLE|SEEKING|LOADING)

    uint8_t play_state = STOPPED; // Current playback state (STOPPED|STARTING|PLAYING|STOPPING)
    sf_count_t file_read_pos = 0; // Current file read position (frames)
    uint8_t loop = 0; // 1 to loop at end of song
    bool looped = false; // True if started playing a loop (not first time)
    sf_count_t loop_start = 0; // Start of loop in frames from start of file
    sf_count_t loop_start_src = -1; // Start of loop in frames from start after SRC
    sf_count_t loop_end; // End of loop in frames from start of file
    sf_count_t loop_end_src; // End of loop in frames from start after SRC
    sf_count_t crop_start = 0; // Start of audio (crop) in frames from start of file
    sf_count_t crop_start_src = -1; // Start of audio (crop) in frames from start after SRC
    sf_count_t crop_end; // End of audio (crop) in frames from start of file
    sf_count_t crop_end_src; // End of audio (crop) in frames from start after SRC
    float gain = 1.0; // Audio level (volume) 0..1
    int track_a = -1; // Which track to playback to left output (-1 to mix all stereo pairs)
    int track_b = -1; // Which track to playback to right output (-1 to mix all stereo pairs)
    unsigned int input_buffer_size = 48000; // Quantity of frames that may be read from file
    unsigned int output_buffer_size; // Quantity of frames that may be SRC
    unsigned int buffer_count = 5; // Factor by which ring buffer is larger than input / SRC buffer
    unsigned int src_quality = SRC_SINC_FASTEST; // SRC quality [0..4]

    // Value of data at last notification
    uint8_t last_play_state = -1;
    uint8_t last_loop = -1;
    sf_count_t last_loop_start = -1;
    sf_count_t last_loop_end = -1;
    sf_count_t last_crop_start = -1;
    sf_count_t last_crop_end = -1;
    float last_position = -1;
    float last_gain = -1.0;
    int last_track_a = -1;
    int last_track_b = -1;
    unsigned int last_input_buffer_size = -1;
    unsigned int last_output_buffer_size = -1;
    unsigned int last_buffer_count = -1;
    unsigned int last_src_quality = -1;

    // ADSR envelope
    int env_state = ENV_IDLE; // Phase of envelope (A,D,S,R,etc.)
    uint8_t env_gate = 0; // True when gate asserted
    float env_level; // Amplitude factor (0..1)
    float env_attack_rate; // Duration of attack phase in seconds
    float last_env_attack_rate; 
    float env_attack_base;
    float env_attack_coef;
    float env_decay_rate; // Duration of decay phase in seconds
    float last_env_decay_rate;
    float env_decay_base;
    float env_decay_coef;
    float env_sustain_level; // Sustain level factor (0..1)
    float last_env_sustain_level;
    float env_release_rate; // Duration of release phase in seconds
    float last_env_release_rate;
    float env_release_base;
    float env_release_coef;
    float env_target_ratio_a;
    float last_env_target_ratio_a;
    float env_target_ratio_dr;
    float last_env_target_ratio_dr;

    struct SF_INFO  sf_info; // Structure containing currently loaded file info
    pthread_t file_thread; // ID of file reader thread
    // Note that jack_ringbuffer handles bytes so need to convert data between bytes and floats

    jack_ringbuffer_t * ringbuffer_a = nullptr; // Used to pass A samples from file reader to jack process
    jack_ringbuffer_t * ringbuffer_b = nullptr; // Used to pass B samples from file reader to jack process
    jack_nframes_t play_pos_frames = 0; // Current playback position in frames since start of audio at play samplerate
    size_t frames = 0; // Quanity of frames after samplerate conversion
    std::string filename;
    uint8_t midi_chan = -1; // MIDI channel to listen
    uint8_t last_note_played = 0; // MIDI note number of last note that triggered playback
    uint8_t held_notes[128]; // MIDI notes numbers that have been pressed but not released
    uint8_t held_note = 0; // 1 if any MIDI notes held
    uint8_t sustain = 0; // True when sustain pedal held
    uint8_t last_sustain = -1;
    float src_ratio = 1.0; // Samplerate ratio of file
    float pitch_bend = 0.0; // Amount of MIDI pitch bend applied +/-range
    uint8_t pitch_bend_range = 2; // Pitchbend range in semitones
    void * cb_object = nullptr; // Pointer to the object hosting the callback function
    cb_fn_t * cb_fn = nullptr; // Pointer to function to receive notification of change
    float pos_notify_delta; // Position time difference to trigger notification

    RubberBand::RubberBandStretcher * stretcher = nullptr; // Time/pitch warp
};
