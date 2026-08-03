"use client";

import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Plays a real rendered audio clip (e.g. an ElevenLabs voice-clone MP3 served by its
 * access token). This is the "real media" path; the browser speech engine in
 * `use-speech` is the zero-cost fallback when no clip was generated.
 */
export function useAudioClip() {
  const [playing, setPlaying] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    const audio = new Audio();
    audio.preload = "auto";
    const onEnd = () => setPlaying(false);
    audio.addEventListener("ended", onEnd);
    audio.addEventListener("pause", onEnd);
    audio.addEventListener("error", onEnd);
    audioRef.current = audio;
    return () => {
      audio.removeEventListener("ended", onEnd);
      audio.removeEventListener("pause", onEnd);
      audio.removeEventListener("error", onEnd);
      audio.pause();
      audioRef.current = null;
    };
  }, []);

  const play = useCallback((url: string, { volume = 1 }: { volume?: number } = {}) => {
    const audio = audioRef.current;
    if (!audio) return Promise.resolve(false);
    audio.src = url;
    audio.volume = Math.max(0, Math.min(1, volume));
    audio.currentTime = 0;
    setPlaying(true);
    // Autoplay can be blocked until the user interacts; the caller triggers this from a
    // click, so it normally succeeds. On rejection we surface false so the caller can
    // fall back to the speech engine.
    return audio
      .play()
      .then(() => true)
      .catch(() => {
        setPlaying(false);
        return false;
      });
  }, []);

  const stop = useCallback(() => {
    const audio = audioRef.current;
    if (audio) {
      audio.pause();
      audio.currentTime = 0;
    }
    setPlaying(false);
  }, []);

  return { play, stop, playing };
}
