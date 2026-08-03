"use client";

import clsx from "clsx";
import {
  BadgeCheck,
  Loader2,
  MessageSquareText,
  Pause,
  Play,
  ShieldAlert,
  Video,
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

type Phase = "loading" | "inbox" | "debrief" | "error";

const VIDEO_MODALITIES = new Set(["video_message", "live_video_call"]);

export function SyntheticMediaSimulator({ token }: { token: string }) {
  const [phase, setPhase] = useState<Phase>("loading");
  const [state, setState] = useState<SimulationState | null>(null);
  const [step, setStep] = useState<ScriptStep | null>(null);
  const [summary, setSummary] = useState<SimulationSummary | null>(null);
  const [narrative, setNarrative] = useState<string[]>([]);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [muted, setMuted] = useState(false);
  const [hasPlayed, setHasPlayed] = useState(false);

  const speech = useSpeech();
  const clip = useAudioClip();
  const stepShownAt = useRef<number>(Date.now());
  const videoRef = useRef<HTMLVideoElement | null>(null);

  const header = state?.header ?? {};
  const isVideo = VIDEO_MODALITIES.has(String(header.modality ?? ""));
  const senderName = header.sender_display_name ?? state?.persona?.display_name ?? "Unknown sender";
  const senderRole = header.sender_role_title ?? state?.persona?.role_title ?? "";
  const modalityNoun = isVideo ? "video message" : "voice note";

  // Real cloned media generated for this scenario, if any.
  const audioToken = state?.media?.audio_token ?? null;
  const videoToken = state?.media?.video_token ?? null;
  const videoPending = state?.media?.video_pending ?? false;
  const hasRealMedia = Boolean(audioToken || videoToken);

  const voiceProfile = useMemo(
    () => ({
      lang: state?.voice_profile?.lang ?? "en-US",
      rate: state?.voice_profile?.rate ?? 1.0,
      pitch: state?.voice_profile?.pitch ?? 0.92,
      volume: muted ? 0 : (state?.voice_profile?.volume ?? 1),
    }),
    [state?.voice_profile, muted],
  );

  const playing = speech.speaking || clip.playing;

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
        setNarrative([data.current_step.speaker_line]);
        setPhase("inbox");
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

  const playMedia = useCallback(() => {
    setHasPlayed(true);

    // If a real talking-head video was rendered, that is the whole media — play it.
    if (videoToken && videoRef.current) {
      const video = videoRef.current;
      if (!video.paused) {
        video.pause();
      } else {
        video.muted = muted;
        void video.play().catch(() => undefined);
      }
      return;
    }

    // Otherwise prefer cloned audio, then fall back to the browser speech engine.
    if (playing) {
      speech.cancel();
      clip.stop();
      return;
    }
    if (muted) return;
    if (audioToken) {
      void clip.play(mediaUrl(audioToken), { volume: voiceProfile.volume }).then((ok) => {
        if (!ok && state?.transcript) speech.speak(state.transcript, voiceProfile);
      });
      return;
    }
    if (state?.transcript) speech.speak(state.transcript, voiceProfile);
  }, [videoToken, audioToken, playing, muted, clip, speech, voiceProfile, state?.transcript]);

  const choose = useCallback(
    async (optionKey: string) => {
      if (!step || pending) return;
      setPending(true);
      setError(null);
      try {
        const result = await postSimulationResponse(token, {
          step_key: step.key,
          response_key: optionKey,
          elapsed_ms: Date.now() - stepShownAt.current,
        });

        if (result.followup_line) {
          setNarrative((rows) => [...rows, result.followup_line!]);
        }

        if (result.finished || result.terminal || !result.next_step) {
          speech.cancel();
          const finalSummary = await completeSimulation(token);
          setSummary(finalSummary);
          setPhase("debrief");
          return;
        }

        setStep(result.next_step);
        setNarrative((rows) => [...rows, result.next_step!.speaker_line]);
        stepShownAt.current = Date.now();
      } catch (err) {
        setError(readError(err));
      } finally {
        setPending(false);
      }
    },
    [step, pending, token, speech],
  );

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
          <ShieldAlert className="mx-auto text-rose-300" size={30} />
          <h1 className="display-font mt-3 text-xl font-bold text-white">Message unavailable</h1>
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

  return (
    <Stage wide>
      <div className="space-y-4 py-4">
        {/* Chat-style header */}
        <div className="sim-panel flex items-center gap-3.5 p-4">
          <div className="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-gradient-to-br from-sky-400/30 to-blue-600/30 ring-1 ring-white/12">
            <span className="text-[0.85rem] font-bold text-white">{initials(senderName)}</span>
          </div>
          <div className="min-w-0 flex-1">
            <div className="truncate text-[0.95rem] font-bold text-white">{senderName}</div>
            {senderRole && senderRole.toLowerCase() !== senderName.toLowerCase() ? (
              <div className="truncate text-[0.76rem] text-white/48">{senderRole}</div>
            ) : null}
          </div>
          <div className="inline-flex items-center gap-1.5 rounded-full bg-white/8 px-2.5 py-1.5 text-[0.7rem] font-semibold text-white/58">
            {isVideo ? <Video size={12} /> : <MessageSquareText size={12} />}
            {modalityNoun}
          </div>
          {hasRealMedia ? (
            <span
              className="rounded bg-sky-400/15 px-1.5 py-0.5 text-[0.58rem] font-bold uppercase tracking-wide text-sky-200"
              title="This message uses real synthetic media cloned from the consented persona"
            >
              {videoToken ? "Cloned video" : "Cloned voice"}
            </span>
          ) : null}
          <button
            type="button"
            onClick={() => {
              if (!muted) {
                speech.cancel();
                clip.stop();
              }
              setMuted((value) => !value);
            }}
            className="grid h-9 w-9 place-items-center rounded-lg bg-white/8 text-white/65 transition hover:bg-white/14 hover:text-white"
            aria-label={muted ? "Unmute playback" : "Mute playback"}
          >
            {muted ? <VolumeX size={16} /> : <Volume2 size={16} />}
          </button>
        </div>

        {/* Media player */}
        <div className="sim-panel overflow-hidden">
          {isVideo ? (
            <div className="relative aspect-video w-full overflow-hidden bg-gradient-to-br from-[#12233f] via-[#0d1a30] to-[#081426]">
              {videoToken ? (
                // Real talking-head video generated from the consented face + cloned audio.
                <video
                  ref={videoRef}
                  src={mediaUrl(videoToken)}
                  className="h-full w-full object-cover"
                  playsInline
                  onPlay={() => setHasPlayed(true)}
                />
              ) : (
                <>
                  {/* Abstract stand-in used when only cloned audio (or nothing) exists. */}
                  <div className="absolute inset-0 grid place-items-center">
                    <div
                      className={clsx(
                        "grid h-32 w-32 place-items-center rounded-full bg-gradient-to-br from-sky-400/25 to-blue-700/30 ring-1 ring-white/12 transition-transform duration-700",
                        playing && "scale-[1.03]",
                      )}
                    >
                      <span className="display-font text-4xl font-bold text-white/85">{initials(senderName)}</span>
                    </div>
                  </div>
                  {playing ? (
                    <div className="sim-scanline pointer-events-none absolute inset-x-0 h-16 bg-gradient-to-b from-transparent via-sky-300/8 to-transparent" />
                  ) : null}
                </>
              )}
              {videoPending ? (
                <div className="absolute inset-x-0 top-3 mx-auto w-max rounded-md bg-amber-500/20 px-2.5 py-1 text-[0.66rem] font-semibold text-amber-100 backdrop-blur">
                  Rendering talking-head video…
                </div>
              ) : null}
              <div className="absolute bottom-3 left-3 rounded-md bg-black/50 px-2 py-1 font-mono text-[0.68rem] text-white/70 backdrop-blur">
                {senderName} · {playing ? "live" : "paused"}
              </div>
            </div>
          ) : (
            <div className="flex items-center gap-4 bg-white/[0.03] px-5 py-6">
              <button
                type="button"
                onClick={playMedia}
                className="grid h-14 w-14 shrink-0 place-items-center rounded-full bg-sky-500 text-white shadow-lg transition hover:bg-sky-400 active:scale-95"
                aria-label={playing ? "Pause voice note" : "Play voice note"}
              >
                {playing ? <Pause size={22} /> : <Play size={22} className="ml-0.5" />}
              </button>
              <div className="min-w-0 flex-1">
                <div className="flex h-10 items-end gap-[3px]">
                  {WAVEFORM.map((height, index) => {
                    // Cloned-audio playback has no progress signal, so animate all bars
                    // while it plays; browser TTS drives the fill from its progress.
                    const lit = clip.playing || speech.progress * WAVEFORM.length > index;
                    return (
                      <span
                        key={index}
                        className={clsx(
                          "flex-1 rounded-full transition-colors",
                          lit ? "bg-sky-300" : "bg-white/16",
                          clip.playing && "sim-wave-bar",
                        )}
                        style={{ height: `${height}%`, animationDelay: `${index * 60}ms` }}
                      />
                    );
                  })}
                </div>
                <div className="numeric mt-2 font-mono text-[0.7rem] text-white/45">
                  {playing ? "Playing…" : hasPlayed ? "Played" : "Tap to play"}
                </div>
              </div>
            </div>
          )}

          {isVideo ? (
            <div className="border-t border-white/8 px-5 py-3.5">
              <button type="button" onClick={playMedia} className="sim-button">
                {playing ? <Pause size={15} /> : <Play size={15} />}
                {playing ? "Pause" : hasPlayed ? "Play again" : "Play message"}
              </button>
            </div>
          ) : null}
        </div>

        {/* Requested action — the ask, stated plainly */}
        {header.requested_action ? (
          <div className="sim-panel border-l-2 border-l-amber-400/60 p-4">
            <div className="text-[0.63rem] font-bold uppercase tracking-[0.16em] text-amber-200/70">
              What you are being asked to do
            </div>
            <p className="mt-1.5 text-[0.92rem] font-semibold leading-relaxed text-white/90">
              {header.requested_action}
            </p>
          </div>
        ) : null}

        {/* Narrative so far */}
        <div className="space-y-2.5">
          {narrative.map((line, index) => (
            <p
              key={`${index}-${line.slice(0, 16)}`}
              className="animate-rise rounded-xl bg-white/[0.045] px-4 py-3 text-[0.9rem] leading-relaxed text-white/82 ring-1 ring-white/8"
            >
              {line}
            </p>
          ))}
        </div>

        {/* Tells the difficulty level allows to be visible before deciding */}
        {state?.visible_artifacts?.length ? (
          <div className="sim-panel p-4">
            <div className="flex items-center gap-2 text-[0.66rem] font-bold uppercase tracking-[0.15em] text-white/45">
              <BadgeCheck size={13} className="text-sky-300" />
              Something feels off
            </div>
            <ul className="mt-3 space-y-2">
              {state.visible_artifacts.map((artifact) => (
                <li key={artifact.key} className="flex gap-2.5 text-[0.82rem] leading-relaxed text-white/68">
                  <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-sky-300" />
                  <span>
                    <span className="font-semibold text-white/85">{artifact.label}.</span> {artifact.detail}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        {/* Decision */}
        {step ? (
          <div className="space-y-2.5 pt-1">
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
                onClick={() => choose(option.key)}
              >
                <span className="mt-0.5 h-2 w-2 shrink-0 rounded-full bg-sky-400/70" />
                <span className="flex-1">{option.label}</span>
                {pending ? <Loader2 size={15} className="mt-0.5 shrink-0 animate-spin opacity-50" /> : null}
              </button>
            ))}
          </div>
        ) : null}

        {!speech.supported && !hasRealMedia ? (
          <p className="rounded-lg border border-amber-400/25 bg-amber-400/10 px-3.5 py-2.5 text-[0.78rem] text-amber-100">
            Your browser cannot synthesise speech, so the message is shown as a transcript. The exercise still works.
          </p>
        ) : null}
      </div>
    </Stage>
  );
}

/* ---------------------------------------------------------------- helpers */

const WAVEFORM = [28, 46, 72, 54, 88, 62, 40, 76, 94, 58, 34, 68, 82, 48, 30, 64, 90, 52, 38, 70, 44, 60, 86, 42, 32];

function Stage({ children, wide = false }: { children: React.ReactNode; wide?: boolean }) {
  return (
    <main className="sim-stage px-4 py-6 md:px-6">
      <div className={clsx("mx-auto w-full", wide ? "max-w-2xl" : "max-w-lg")}>{children}</div>
    </main>
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
