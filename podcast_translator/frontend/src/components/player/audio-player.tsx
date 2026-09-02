'use client'

import React, { useRef, useState, useEffect, useCallback } from 'react'
import { Play, Pause, Volume2, VolumeX } from 'lucide-react'

interface AudioPlayerProps {
  src: string
  className?: string
}

function formatTime(seconds: number): string {
  if (!seconds || isNaN(seconds)) return '0:00'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.floor(seconds % 60)
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  return `${m}:${String(s).padStart(2, '0')}`
}

const SPEEDS = [0.5, 0.75, 1, 1.25, 1.5, 2]

export function AudioPlayer({ src, className = '' }: AudioPlayerProps) {
  const audioRef = useRef<HTMLAudioElement>(null)
  const progressRef = useRef<HTMLDivElement>(null)

  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [speed, setSpeed] = useState(1)
  const [isMuted, setIsMuted] = useState(false)
  const [isDragging, setIsDragging] = useState(false)

  // Audio event handlers
  useEffect(() => {
    const audio = audioRef.current
    if (!audio) return

    const handleTimeUpdate = () => {
      if (!isDragging) {
        setCurrentTime(audio.currentTime)
      }
    }
    const handleLoadedMetadata = () => setDuration(audio.duration)
    const handleEnded = () => setIsPlaying(false)

    audio.addEventListener('timeupdate', handleTimeUpdate)
    audio.addEventListener('loadedmetadata', handleLoadedMetadata)
    audio.addEventListener('ended', handleEnded)

    return () => {
      audio.removeEventListener('timeupdate', handleTimeUpdate)
      audio.removeEventListener('loadedmetadata', handleLoadedMetadata)
      audio.removeEventListener('ended', handleEnded)
    }
  }, [isDragging])

  const togglePlay = useCallback(() => {
    const audio = audioRef.current
    if (!audio) return

    if (isPlaying) {
      audio.pause()
    } else {
      audio.play()
    }
    setIsPlaying(!isPlaying)
  }, [isPlaying])

  const toggleMute = useCallback(() => {
    const audio = audioRef.current
    if (!audio) return
    audio.muted = !isMuted
    setIsMuted(!isMuted)
  }, [isMuted])

  const cycleSpeed = useCallback(() => {
    const audio = audioRef.current
    if (!audio) return
    const currentIndex = SPEEDS.indexOf(speed)
    const nextIndex = (currentIndex + 1) % SPEEDS.length
    const newSpeed = SPEEDS[nextIndex]
    audio.playbackRate = newSpeed
    setSpeed(newSpeed)
  }, [speed])

  const handleSeek = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    const audio = audioRef.current
    const bar = progressRef.current
    if (!audio || !bar || !duration) return

    const rect = bar.getBoundingClientRect()
    const x = Math.max(0, Math.min(e.clientX - rect.left, rect.width))
    const percent = x / rect.width
    audio.currentTime = percent * duration
    setCurrentTime(percent * duration)
  }, [duration])

  const progress = duration > 0 ? (currentTime / duration) * 100 : 0

  return (
    <div className={`audio-player ${className}`}>
      <audio ref={audioRef} src={src} preload="metadata" />

      {/* Play/Pause Button */}
      <button
        className="audio-player__play-btn"
        onClick={togglePlay}
        aria-label={isPlaying ? '暂停' : '播放'}
        id="audio-player-toggle"
      >
        {isPlaying ? (
          <Pause className="audio-player__play-icon" />
        ) : (
          <Play className="audio-player__play-icon" style={{ marginLeft: 2 }} />
        )}
      </button>

      {/* Seek Bar */}
      <div
        ref={progressRef}
        className="audio-player__track"
        onClick={handleSeek}
        onMouseDown={() => setIsDragging(true)}
        onMouseUp={() => setIsDragging(false)}
        role="slider"
        aria-label="播放进度"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(progress)}
      >
        <div
          className="audio-player__track-fill"
          style={{ width: `${progress}%` }}
        />
        <div
          className="audio-player__track-handle"
          style={{ left: `${progress}%` }}
        />
      </div>

      {/* Time */}
      <span className="audio-player__time">
        {formatTime(currentTime)} / {formatTime(duration)}
      </span>

      {/* Mute */}
      <button
        className="audio-player__control-btn"
        onClick={toggleMute}
        aria-label={isMuted ? '取消静音' : '静音'}
      >
        {isMuted ? (
          <VolumeX className="audio-player__control-icon" />
        ) : (
          <Volume2 className="audio-player__control-icon" />
        )}
      </button>

      {/* Speed */}
      <button
        className="audio-player__speed-btn"
        onClick={cycleSpeed}
        aria-label={`播放速度 ${speed}x`}
        id="audio-player-speed"
      >
        {speed}x
      </button>
    </div>
  )
}
