"use client";

import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Text-to-speech for the voice and synthetic-media simulators, backed by the
 * browser's built-in Web Speech API.
 *
 * This is a deliberate architectural choice, not a shortcut:
 *
 * - **No paid service.** Cloud voice-cloning APIs are the usual way to build a
 *   deepfake demo and they are both expensive and ethically fraught.
 * - **Nothing leaves the device.** No audio is uploaded, generated server-side,
 *   or stored, so the simulation cannot be exfiltrated and reused as real
 *   impersonation material.
 * - **Nothing to clean up.** The "recording" exists only while the page is open.
 *
 * The trade-off is that the voice is synthetic-sounding rather than a clone of a
 * specific person — which is exactly the boundary the platform wants to keep.
 */

export interface SpeechProfile {
  lang?: string;
  rate?: number;
  pitch?: number;
  volume?: number;
  voiceHint?: string;
}

export interface SpeechController {
  supported: boolean;
  speaking: boolean;
  /** Fraction of the current utterance already spoken, 0..1. */
  progress: number;
  speak: (text: string, profile?: SpeechProfile) => void;
  cancel: () => void;
}

export function useSpeech(): SpeechController {
  const [supported, setSupported] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [progress, setProgress] = useState(0);
  const voicesRef = useRef<SpeechSynthesisVoice[]>([]);
  const timerRef = useRef<number | null>(null);

  useEffect(() => {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) return;
    setSupported(true);

    const loadVoices = () => {
      voicesRef.current = window.speechSynthesis.getVoices();
    };
    loadVoices();
    window.speechSynthesis.addEventListener("voiceschanged", loadVoices);

    return () => {
      window.speechSynthesis.removeEventListener("voiceschanged", loadVoices);
      window.speechSynthesis.cancel();
    };
  }, []);

  const clearTimer = useCallback(() => {
    if (timerRef.current !== null) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const cancel = useCallback(() => {
    clearTimer();
    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      window.speechSynthesis.cancel();
    }
    setSpeaking(false);
    setProgress(0);
  }, [clearTimer]);

  const speak = useCallback(
    (text: string, profile: SpeechProfile = {}) => {
      if (typeof window === "undefined" || !("speechSynthesis" in window) || !text?.trim()) {
        return;
      }
      window.speechSynthesis.cancel();
      clearTimer();

      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = profile.lang ?? "en-US";
      utterance.rate = clamp(profile.rate ?? 1, 0.5, 2);
      utterance.pitch = clamp(profile.pitch ?? 1, 0, 2);
      utterance.volume = clamp(profile.volume ?? 1, 0, 1);

      const voices = voicesRef.current.length ? voicesRef.current : window.speechSynthesis.getVoices();
      const preferred =
        (profile.voiceHint &&
          voices.find((voice) => voice.name.toLowerCase().includes(profile.voiceHint!.toLowerCase()))) ||
        voices.find((voice) => voice.lang === utterance.lang) ||
        voices.find((voice) => voice.lang?.startsWith(utterance.lang.slice(0, 2)));
      if (preferred) utterance.voice = preferred;

      // `boundary` events are unreliable across engines, so drive the progress
      // bar from an estimated duration (~14 characters per second at rate 1).
      const estimatedMs = Math.max(1200, (text.length / (14 * utterance.rate)) * 1000);
      const startedAt = Date.now();

      utterance.onstart = () => {
        setSpeaking(true);
        setProgress(0);
        timerRef.current = window.setInterval(() => {
          setProgress(Math.min(0.99, (Date.now() - startedAt) / estimatedMs));
        }, 90);
      };
      const finish = () => {
        clearTimer();
        setSpeaking(false);
        setProgress(1);
      };
      utterance.onend = finish;
      utterance.onerror = finish;

      window.speechSynthesis.speak(utterance);
    },
    [clearTimer],
  );

  useEffect(() => cancel, [cancel]);

  return { supported, speaking, progress, speak, cancel };
}

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}
