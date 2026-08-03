"use client";

import clsx from "clsx";
import {
  Building2,
  Loader2,
  Mic,
  Phone,
  PhoneCall,
  PhoneOff,
  Volume2,
  VolumeX,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { SimulationDebrief } from "@/components/simulation-debrief";
import {
  completeSimulation,
  getSimulation,
  mediaUrl,
  postSimulationResponse,
  type ScriptStep,
  type SimulationState,
  type SimulationSummary,
} from "@/lib/client-api";
import { useAudioClip } from "@/lib/use-audio-clip";
import { useSpeech } from "@/lib/use-speech";

type Phase = "loading" | "ringing" | "in-call" | "debrief" | "error";

interface Transcript {
  speaker: "caller" | "you";
  text: string;
}

export function VoiceCallSimulator({ token }: { token: string }) {
  const [phase, setPhase] = useState<Phase>("loading");
  const [state, setState] = useState<SimulationState | null>(null);
  const [step, setStep] = useState<ScriptStep | null>(null);
  const [transcript, setTranscript] = useState<Transcript[]>([]);
  const [summary, setSummary] = useState<SimulationSummary | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [muted, setMuted] = useState(false);
  const [seconds, setSeconds] = useState(0);

  const speech = useSpeech();
  const clip = useAudioClip();
  const stepShownAt = useRef<number>(Date.now());
  const transcriptEndRef = useRef<HTMLDivElement>(null);

  const voiceProfile = useMemo(
    () => ({
      lang: state?.voice_profile?.lang ?? "en-US",
      rate: state?.voice_profile?.rate ?? 1.02,
      pitch: state?.voice_profile?.pitch ?? 0.95,
      volume: muted ? 0 : (state?.voice_profile?.volume ?? 1),
    }),
    [state?.voice_profile, muted],
  );

  // Real cloned audio (ElevenLabs) is rendered for the caller's opening line. Later lines
  // use the browser speech engine. `speaking` covers both so the UI is consistent.
  const clonedAudioToken = state?.media?.audio_token ?? null;
  const usingRealVoice = Boolean(clonedAudioToken);
  const speaking = speech.speaking || clip.playing;

  const sayCaller = useCallback(
    (text: string, { opener = false }: { opener?: boolean } = {}) => {
      if (muted) return;
      // The cloned clip is the opening line only, so use it there and fall back to the
      // speech engine (which never rejects) if the browser blocks audio autoplay.
      if (opener && clonedAudioToken) {
        void clip.play(mediaUrl(clonedAudioToken), { volume: voiceProfile.volume }).then((ok) => {
          if (!ok) speech.speak(text, voiceProfile);
        });
        return;
      }
      speech.speak(text, voiceProfile);
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [muted, clonedAudioToken, voiceProfile],
  );

  /* ------------------------------------------------------------------ load */

  useEffect(() => {
    let cancelled = false;
    getSimulation(token)
      .then((data) => {
        if (cancelled) return;
        setState(data);
        if (data.finished || !data.current_step) {
          return completeSimulation(token).then((result) => {
            if (cancelled) return;
            setSummary(result);
            setPhase("debrief");
          });
        }
        setStep(data.current_step);
        setPhase("ringing");
      })
      .catch((err) => {
        if (cancelled) return;
        setError(readError(err));
        setPhase("error");
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  /* -------------------------------------------------------------- call timer */

  useEffect(() => {
    if (phase !== "in-call") return;
    const id = window.setInterval(() => setSeconds((value) => value + 1), 1000);
    return () => window.clearInterval(id);
  }, [phase]);

  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [transcript]);

  /* ------------------------------------------------------------- interaction */

  const answer = useCallback(() => {
    if (!step) return;
    setPhase("in-call");
    setTranscript([{ speaker: "caller", text: step.speaker_line }]);
    stepShownAt.current = Date.now();
    // Opening line uses the real cloned voice when one was generated.
    sayCaller(step.speaker_line, { opener: true });
  }, [step, sayCaller]);

  const stopAudio = useCallback(() => {
    speech.cancel();
    clip.stop();
  }, [speech, clip]);

  const declineCall = useCallback(async () => {
    stopAudio();
    setPending(true);
    try {
      const result = await completeSimulation(token);
      setSummary(result);
      setPhase("debrief");
    } catch (err) {
      setError(readError(err));
      setPhase("error");
    } finally {
      setPending(false);
    }
  }, [stopAudio, token]);

  const choose = useCallback(
    async (optionKey: string, optionLabel: string) => {
      if (!step || pending) return;
      stopAudio();
      setPending(true);
      setError(null);
      setTranscript((rows) => [...rows, { speaker: "you", text: optionLabel }]);

      try {
        const result = await postSimulationResponse(token, {
          step_key: step.key,
          response_key: optionKey,
          elapsed_ms: Date.now() - stepShownAt.current,
        });

        if (result.followup_line) {
          setTranscript((rows) => [...rows, { speaker: "caller", text: result.followup_line! }]);
          if (!result.terminal) sayCaller(result.followup_line);
        }

        if (result.finished || result.terminal || !result.next_step) {
          const finalSummary = await completeSimulation(token);
          setSummary(finalSummary);
          setPhase("debrief");
          return;
        }

        setStep(result.next_step);
        stepShownAt.current = Date.now();
        // Let the caller's reaction land before the next pressure line.
        window.setTimeout(() => {
          setTranscript((rows) => [...rows, { speaker: "caller", text: result.next_step!.speaker_line }]);
          sayCaller(result.next_step!.speaker_line);
        }, 900);
      } catch (err) {
        setError(readError(err));
      } finally {
        setPending(false);
      }
    },
    [step, pending, speech, token, muted, voiceProfile],
  );

  /* ----------------------------------------------------------------- render */

  if (phase === "loading") {
    return (
      <Stage>
        <div className="flex min-h-[60vh] items-center justify-center">
          <Loader2 className="animate-spin text-sky-300" size={30} />
        </div>
      </Stage>
    );
  }

  if (phase === "error") {
    return (
      <Stage>
        <div className="sim-panel mx-auto mt-16 max-w-md p-7 text-center">
          <PhoneOff className="mx-auto text-rose-300" size={30} />
          <h1 className="display-font mt-3 text-xl font-bold text-white">Call unavailable</h1>
          <p className="mt-2 text-sm leading-relaxed text-white/60">{error}</p>
        </div>
      </Stage>
    );
  }

  if (phase === "debrief" && summary) {
    return (
      <Stage wide>
        <SimulationDebrief summary={summary} />
      </Stage>
    );
  }

  const header = state?.header ?? {};
  const callerName = header.spoofed_display_name ?? state?.persona?.display_name ?? "Unknown caller";
  const callerNumber = header.caller_id_display ?? "Unknown number";
  const callerLabel = header.caller_id_label ?? "Inbound call";

  if (phase === "ringing") {
    return (
      <Stage>
        <div className="flex min-h-[86vh] flex-col items-center justify-center">
          <div className="text-[0.68rem] font-bold uppercase tracking-[0.24em] text-white/40">
            Incoming call
          </div>

          <div className="sim-ringing mt-9 grid h-28 w-28 place-items-center rounded-full bg-gradient-to-br from-sky-400/25 to-blue-600/25 ring-1 ring-white/15">
            <span className="display-font text-3xl font-bold text-white">{initials(callerName)}</span>
          </div>

          <h1 className="display-font mt-7 text-center text-[1.6rem] font-bold text-white">{callerName}</h1>
          <p className="numeric mt-1.5 font-mono text-[0.95rem] tracking-wide text-white/62">{callerNumber}</p>
          <div className="mt-3 inline-flex items-center gap-1.5 rounded-full bg-white/8 px-3 py-1.5 text-[0.74rem] font-semibold text-white/62">
            <Building2 size={13} />
            {callerLabel}
          </div>

          <div className="mt-14 flex items-center gap-14">
            <button
              type="button"
              onClick={declineCall}
              disabled={pending}
              className="group flex flex-col items-center gap-2.5"
              aria-label="Decline call"
            >
              <span className="grid h-16 w-16 place-items-center rounded-full bg-rose-500 text-white shadow-lg transition group-hover:bg-rose-400 group-active:scale-95">
                <PhoneOff size={24} />
              </span>
              <span className="text-[0.74rem] font-semibold text-white/55">Decline</span>
            </button>

            <button
              type="button"
              onClick={answer}
              className="group flex flex-col items-center gap-2.5"
              aria-label="Answer call"
            >
              <span className="grid h-16 w-16 place-items-center rounded-full bg-emerald-500 text-white shadow-lg transition group-hover:bg-emerald-400 group-active:scale-95">
                <Phone size={24} />
              </span>
              <span className="text-[0.74rem] font-semibold text-white/55">Answer</span>
            </button>
          </div>
        </div>
      </Stage>
    );
  }

  return (
    <Stage wide>
      <div className="mx-auto flex min-h-[92vh] max-w-3xl flex-col">
        {/* Call bar */}
        <div className="sim-panel flex items-center gap-3.5 p-4">
          <div className="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-gradient-to-br from-sky-400/30 to-blue-600/30 ring-1 ring-white/12">
            <span className="text-[0.85rem] font-bold text-white">{initials(callerName)}</span>
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span className="truncate text-[0.95rem] font-bold text-white">{callerName}</span>
              {usingRealVoice ? (
                <span
                  className="shrink-0 rounded bg-sky-400/15 px-1.5 py-0.5 text-[0.58rem] font-bold uppercase tracking-wide text-sky-200"
                  title="Playing a real cloned voice generated for this persona"
                >
                  Cloned voice
                </span>
              ) : null}
            </div>
            <div className="numeric mt-0.5 flex items-center gap-2 font-mono text-[0.74rem] text-white/50">
              <span className="inline-flex items-center gap-1.5">
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-400" />
                {formatDuration(seconds)}
              </span>
              <span className="text-white/25">·</span>
              <span className="truncate">{callerNumber}</span>
            </div>
          </div>

          {speaking ? <SpeakingBars /> : null}

          <button
            type="button"
            onClick={() => {
              if (!muted) stopAudio();
              setMuted((value) => !value);
            }}
            className="grid h-9 w-9 place-items-center rounded-lg bg-white/8 text-white/65 transition hover:bg-white/14 hover:text-white"
            aria-label={muted ? "Unmute caller audio" : "Mute caller audio"}
          >
            {muted ? <VolumeX size={16} /> : <Volume2 size={16} />}
          </button>
          <button
            type="button"
            onClick={declineCall}
            disabled={pending}
            className="grid h-9 w-9 place-items-center rounded-lg bg-rose-500/85 text-white transition hover:bg-rose-500 disabled:opacity-50"
            aria-label="Hang up"
          >
            <PhoneOff size={16} />
          </button>
        </div>

        {!speech.supported && !usingRealVoice ? (
          <p className="mt-3 rounded-lg border border-amber-400/25 bg-amber-400/10 px-3.5 py-2.5 text-[0.78rem] text-amber-100">
            Your browser cannot synthesise speech, so the call is shown as text only. The exercise still works.
          </p>
        ) : null}

        {/* Transcript */}
        <div className="mt-4 flex-1 space-y-3 overflow-y-auto pb-4">
          {transcript.map((line, index) => (
            <div
              key={`${index}-${line.text.slice(0, 18)}`}
              className={clsx("animate-rise flex", line.speaker === "you" ? "justify-end" : "justify-start")}
            >
              <div
                className={clsx(
                  "max-w-[85%] rounded-2xl px-4 py-3 text-[0.9rem] leading-relaxed",
                  line.speaker === "you"
                    ? "rounded-br-sm bg-sky-500/22 text-sky-50 ring-1 ring-sky-400/25"
                    : "rounded-bl-sm bg-white/7 text-white/88 ring-1 ring-white/10",
                )}
              >
                <div className="mb-1 flex items-center gap-1.5 text-[0.63rem] font-bold uppercase tracking-[0.14em] opacity-55">
                  {line.speaker === "you" ? (
                    <>
                      <Mic size={10} /> You
                    </>
                  ) : (
                    <>
                      <PhoneCall size={10} /> {callerName}
                    </>
                  )}
                </div>
                {line.text}
              </div>
            </div>
          ))}
          <div ref={transcriptEndRef} />
        </div>

        {/* Response options */}
        {step ? (
          <div className="sticky bottom-0 space-y-2.5 bg-gradient-to-t from-[#040914] via-[#040914]/95 to-transparent pb-6 pt-4">
            {step.hint ? (
              <p className="px-1 text-[0.74rem] italic leading-relaxed text-white/38">{step.hint}</p>
            ) : null}
            {error ? (
              <p className="rounded-lg border border-rose-400/25 bg-rose-400/10 px-3 py-2 text-[0.78rem] text-rose-100">
                {error}
              </p>
            ) : null}
            {step.options.map((option) => (
              <button
                key={option.key}
                type="button"
                className="sim-choice"
                disabled={pending}
                onClick={() => choose(option.key, option.label)}
              >
                <span className="mt-0.5 h-2 w-2 shrink-0 rounded-full bg-sky-400/70" />
                <span className="flex-1">{option.label}</span>
                {pending ? <Loader2 size={15} className="mt-0.5 shrink-0 animate-spin opacity-50" /> : null}
              </button>
            ))}
          </div>
        ) : null}
      </div>
    </Stage>
  );
}

/* ---------------------------------------------------------------- helpers */

function Stage({ children, wide = false }: { children: React.ReactNode; wide?: boolean }) {
  return (
    <main className="sim-stage px-4 py-6 md:px-6">
      <div className={clsx("mx-auto w-full", wide ? "max-w-4xl" : "max-w-lg")}>{children}</div>
    </main>
  );
}

function SpeakingBars() {
  return (
    <div className="flex items-end gap-[3px]" aria-hidden="true">
      {[0, 1, 2, 3].map((index) => (
        <span
          key={index}
          className="sim-wave-bar h-3.5 w-[3px] rounded-full bg-sky-300"
          style={{ animationDelay: `${index * 120}ms` }}
        />
      ))}
    </div>
  );
}

function initials(name: string) {
  return name
    .split(" ")
    .map((part) => part[0] ?? "")
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

function formatDuration(totalSeconds: number) {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

function readError(error: unknown): string {
  if (error && typeof error === "object" && "message" in error) {
    const raw = String((error as Error).message);
    try {
      const parsed = JSON.parse(raw);
      return typeof parsed === "string" ? parsed : raw;
    } catch {
      return raw;
    }
  }
  return "Something went wrong.";
}
