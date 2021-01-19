/** Class providing Standard MIDI File format parsing and handling
*/
#pragma once

#include "track.h" //provides Track class
#include <cstdio> //provides FILE
#include <vector> //provides vector class
#include <map> //provides map class 
#include <string> //provides string

class Smf
{
    public:
        /** Deconstruct SMF object */
        ~Smf();

        /** @brief  Enable debug output
        *   @param  bEnable True to enable, false to disable debug output (Default: true)
        */
       void enableDebug(bool bEnable = true);

        /** @brief  Load a SMF file
        *   @param  sFilename Full path and name of file to load
        *   @retval bool True on success
        */
        bool load(char* sFilename);

        /** @brief  Clear all song data
        */
        void unload();

        /** @brief  Get quantity of tracks in SMF
        *   @retval size_t Quantity of tracks
        */
        size_t getTracks();

        /** @brief  Get duration of longest track
        *   @retval double Duration in milliseconds
        *   @todo   Should Smf class should return duration in ticks, microseconds and seconds?
        */
        double getDuration();

        /** @brief  Get next event since last check or last setPosition
        *   @param  bAdvance True to advance to next event (Default: true)
        *   @retval Event* Pointer to the next event
        */
        Event* getNextEvent(bool bAdvance = true);

        /** @brief  Set event cursor position to time
        *   @param  nTime Time in milliseconds
        *   @todo   Should Smf class setPosition be in ticks, seconds, microseconds?
        */
        void setPosition(size_t nTime);

        /** @brief  Get MIDI file format
        *   @retval uint8_t SMF format [0|1|2]
        */
       uint8_t getFormat();

        /** @brief  Get quantity of Events in track
        *   @retval uint32_t Quantity of events in track
        */
        uint32_t getEvents(size_t nTrack);

        /** @brief  Get ticks per quarter note
        *   @retval uint16_t Ticks per quarter note
        */
        uint16_t getTicksPerQuarterNote();

        /** @brief  Get the track which contains the last retrieved event
        *   @retval size_t Track index
        */
        size_t getCurrentTrack();


    private:
        /** @brief  Write 8-bit word to file
        *   @param  nValue 8-bit word to write
        *   @param  pfile Pointer to open file
        *   @retval int Quanity of bytes actually written to file
        */
        int fileWrite8(uint8_t value, FILE *pFile);

        /** @brief  Read 8-bit word from file
        *   @param  pfile Pointer to open file
        *   @retval uint8_t 8-bit word read from file
        */
        uint8_t fileRead8(FILE* pFile);

        /** @brief  Write 16-bit word to file
        *   @param  nValue 16-bit word  to write
        *   @param  pfile Pointer to open file
        *   @retval int Quanity of bytes actually written to file
        */
        int fileWrite16(uint16_t value, FILE *pFile);

        /** @brief  Read 16-bit word from file
        *   @param  pfile Pointer to open file
        *   @retval uint16_t 16-bit word read from file
        */
        uint16_t fileRead16(FILE* pFile);

        /** @brief  Write 32 bit word to file
        *   @param  nValue 32-bit word to write
        *   @param  pfile Pointer to open file
        *   @retval int Quanity of bytes actually written to file
        */
        int fileWrite32(uint32_t value, FILE *pFile);

        /** @brief  Read 32-bit word from file
        *   @param  pfile Pointer to open file
        *   @retval uint8_t 32-bit word read from file
        */
        uint32_t fileRead32(FILE* pFile);

        /** @brief  Read variable length number from file
        *   @param  pfile Pointer to open file
        *   @retval uint32_t Number read from file
        */
        uint32_t fileReadVar(FILE* pFile);

        /** @brief  Read c-string from file
        *   @param  pfile Pointer to open file
        *   @param  pString Pointer to a char buffer to store string
        *   @param  nSize Length of c-string without terminating null character
        *   @retval size_t Quantity of bytes read from file
        */
        size_t fileReadString(FILE *pFile, char* pString, size_t nSize);

        // Get the duration of a quater note at position within file measured in ticks
        /** @brief  Get tempo in microseconds per quarter note at position in SMF
        *   @param  nTime Position in ticks at which to get tempo
        *   @retval uint32_t Quantity of microseconds in a quarter note
        */
        uint32_t getMicrosecondsPerQuarterNote(uint32_t nTime);


        std::vector<Track*> m_vTracks; // Vector of tracks within SMF
        std::map<uint32_t, uint32_t> m_mTempoMap; // Map of tempo changes (duration of quarter note in microseconds) indexed by time in ticks
        std::string m_sFilename; // Full path and filename
        bool m_bDebug = false; // True for debug output
        bool m_bTimecodeBased; // True for timecode based time. False for metrical based time.
        uint16_t m_nFormat = 0; // MIDI file format [0|1|2]
        uint16_t m_nTracks = 0; // Quantity of MIDI tracks reported by IFF header (actual quantity deduced by quantity of MTrk blocks in IFF)
        uint8_t m_nSmpteFps = 0; // SMPTE frames per second (for timecode based time)
        uint8_t m_nSmpteResolution = 0; // SMPTE subframe resolution  (for timecode based time)
        uint16_t m_nTicksPerQuarterNote = 96; // Ticks per quarter note (for metrical based time)
        uint16_t m_nManufacturerId = 0; // Manufacturers MIDI ID (if embeded)
        uint32_t m_nDurationInTicks = 0; // Duration of song in ticks
        size_t m_nPosition = 0; // Event cursor position in ticks
        size_t m_nCurrentTrack = 0; // Index of track that last event was retrieved 
        double m_fTickDuration = 500.0 / 96; // Duration of tick in milliseconds at event cursor position
        double m_fDuration = 0; // Duration of song in seconds
};