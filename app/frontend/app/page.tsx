"use client";

import type React from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  Bell,
  BookOpen,
  Bookmark,
  Box,
  Camera,
  Check,
  ChevronLeft,
  Compass,
  Crown,
  Download,
  Eye,
  Flag,
  Gem,
  Heart,
  Home,
  Image as ImageIcon,
  ImagePlus,
  Landmark,
  LocateFixed,
  Mail,
  Map,
  MapPin,
  Maximize2,
  Move,
  PackageCheck,
  Palette,
  RefreshCw,
  Rotate3D,
  RotateCcw,
  RotateCw,
  Route,
  Save,
  Search,
  Send,
  Share2,
  Sparkles,
  Trash2,
  Truck,
  Undo2,
  Unlock,
  User,
  Wallet,
  WandSparkles,
  X
} from "lucide-react";
import { ModelViewer } from "../components/ModelViewer";
import { ServiceWorkerRegister } from "../components/ServiceWorkerRegister";
import {
  checkVisit,
  createEditorSession,
  createGuestSession,
  createPretravelConcept,
  fetchDestinationCulture,
  fetchDestinationParts,
  fetchDestinations,
  fetchFigurines,
  fetchJob,
  fetchMe,
  finalizeEditor3D,
  patchEditorLayers,
  refineEditor2D,
  setAuthToken,
  startEmailLogin
} from "../lib/api";
import { getApiBase } from "../lib/config";
import type {
  Destination,
  DestinationCulture,
  EditorLayer,
  Figurine,
  JobStatus,
  PartAsset,
  PublicDataSource,
  Screen
} from "../lib/types";

const API_BASE = getApiBase();
const REVIEW_UNLOCK_EMAIL = "jjoonghui@gmail.com";
const ACTIVE_JOB_STORAGE_KEY = "jogak_active_job_id";
const SAVED_PREVIEWS_STORAGE_PREFIX = "jogak_saved_previews_v1";

type JobNotice = {
  job: JobStatus;
  title: string;
  message: string;
};

type SavedPreview = {
  destinationId: string;
  figurineId: string;
  conceptUrl: string;
  glbUrl?: string | null;
  updatedAt: string;
};

const screenTitles: Partial<Record<Screen, string>> = {
  home: "나의 조각장",
  explore: "탐색",
  destination: "관광지 알아보기",
  maker: "방문 전 만들기",
  prepreview: "방문 전 조각",
  parts: "해금 부품",
  unlock: "장소 해금",
  customize: "스타일 선택",
  generate: "제작 중",
  editor: "부품 배치",
  preview: "3D 미리보기",
  story: "이야기",
  print: "제작 요청",
  shipping: "배송",
  profile: "내정보"
};

function estimatedProgressCeiling(job: JobStatus): number {
  if (job.status === "done" || job.status === "failed") return 100;
  const state = job.current_state || "queued";
  const serverProgress = job.progress || 0;
  if (state.includes("queued")) return 14;
  if (state.includes("dna")) return 24;
  if (state.includes("openai")) return 54;
  if (state.includes("hunyuan_part")) return Math.min(90, serverProgress + 3);
  if (state.includes("blender_part")) return Math.min(96, serverProgress + 3);
  if (state.includes("hunyuan")) return job.type === "hunyuan_final" ? Math.min(72, serverProgress + 3) : 90;
  return Math.max(job.progress || 0, 78);
}

function partProgressText(state: string): string | null {
  const match = state.match(/hunyuan_part_(\d+)_(\d+)/);
  if (!match) return null;
  return `부품 ${match[1]}/${match[2]} 입체화`;
}

function jobStatusLabel(job: JobStatus | null): string {
  if (!job) return "대기";
  if (job.status === "done") return "완료";
  if (job.status === "failed") return "실패";
  const state = job.current_state || "queued";
  const partLabel = partProgressText(state);
  if (partLabel) return partLabel;
  if (state.includes("openai")) return job.type === "editor_refine_2d" ? "자연 배치 2D 생성" : "2D 프리뷰 생성";
  if (state.includes("hunyuan_character")) return "캐릭터 입체화";
  if (state.includes("blender_part")) return "최종 조립";
  if (state.includes("hunyuan")) return job.type === "hunyuan_final" ? "3D 조각 준비" : "3D 프리뷰 변환";
  if (state.includes("dna")) return "문화 DNA 정리";
  return "대기열 확인";
}

function previewStorageKey(email: string) {
  return `${SAVED_PREVIEWS_STORAGE_PREFIX}:${email.trim().toLowerCase() || "guest"}`;
}

function readSavedPreviews(email: string): Record<string, SavedPreview> {
  if (typeof window === "undefined") return {};
  try {
    return JSON.parse(window.localStorage.getItem(previewStorageKey(email)) || "{}") as Record<string, SavedPreview>;
  } catch {
    return {};
  }
}

function writeSavedPreviews(email: string, previews: Record<string, SavedPreview>) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(previewStorageKey(email), JSON.stringify(previews));
}

function assetPublicUrl(asset: Figurine["assets"][number] | undefined) {
  if (!asset) return null;
  if (asset.url) return asset.url;
  return asset.path.startsWith("http") ? asset.path : null;
}

function savedPreviewFromFigurine(figurine: Figurine): SavedPreview | null {
  const conceptAsset = figurine.assets.find((asset) => asset.type === "pretravel_concept_2d")
    || figurine.assets.find((asset) => asset.type === "concept_2d");
  const conceptUrl = assetPublicUrl(conceptAsset);
  if (!conceptUrl) return null;
  return {
    destinationId: figurine.destination_id,
    figurineId: figurine.id,
    conceptUrl,
    glbUrl: assetPublicUrl(figurine.assets.find((asset) => asset.type === "preview_glb")),
    updatedAt: figurine.updated_at || figurine.created_at || new Date().toISOString()
  };
}

function mergeSavedPreviews(current: Record<string, SavedPreview>, figurines: Figurine[]) {
  const next = { ...current };
  for (const figurine of figurines) {
    const preview = savedPreviewFromFigurine(figurine);
    if (!preview) continue;
    const existing = next[preview.destinationId];
    if (!existing || new Date(preview.updatedAt).getTime() >= new Date(existing.updatedAt).getTime()) {
      next[preview.destinationId] = preview;
    }
  }
  return next;
}

export default function JogakApp() {
  const [screen, setScreen] = useState<Screen>("login");
  const [storyReturnScreen, setStoryReturnScreen] = useState<Screen>("destination");
  const [jobReturnScreen, setJobReturnScreen] = useState<Screen>("home");
  const [destinations, setDestinations] = useState<Destination[]>([]);
  const [allDestinations, setAllDestinations] = useState<Destination[]>([]);
  const [selectedDestination, setSelectedDestination] = useState<Destination | null>(null);
  const [query, setQuery] = useState("");
  const [email, setEmail] = useState("");
  const [userName, setUserName] = useState("");
  const [userEmail, setUserEmail] = useState("");
  const [loginNotice, setLoginNotice] = useState("");
  const [prompt, setPrompt] = useState("차분한 박물관 탐험가 느낌, 국립중앙박물관의 석재 광장과 전시 공간 분위기를 옷과 밑판에만 은은하게");
  const [style, setStyle] = useState("책상 피규어");
  const [photoFile, setPhotoFile] = useState<File | null>(null);
  const [photoName, setPhotoName] = useState("");
  const [currentFigurineId, setCurrentFigurineId] = useState<string | null>(null);
  const [editorSessionId, setEditorSessionId] = useState<string | null>(null);
  const [job, setJob] = useState<JobStatus | null>(null);
  const [jobProgress, setJobProgress] = useState(0);
  const [jobNotice, setJobNotice] = useState<JobNotice | null>(null);
  const [jobPollWarning, setJobPollWarning] = useState("");
  const [unlockNotice, setUnlockNotice] = useState("현재 위치를 확인하면 방문 인증과 부품 해금이 진행됩니다.");
  const [unlockedParts, setUnlockedParts] = useState<string[]>([]);
  const [partAssets, setPartAssets] = useState<PartAsset[]>([]);
  const [cultureData, setCultureData] = useState<DestinationCulture | null>(null);
  const [layers, setLayers] = useState<EditorLayer[]>([]);
  const [selectedLayer, setSelectedLayer] = useState("");
  const [savedPreviews, setSavedPreviews] = useState<Record<string, SavedPreview>>({});
  const [dragState, setDragState] = useState<{ id: string; dx: number; dy: number } | null>(null);
  const [pretravelConceptUrl, setPretravelConceptUrl] = useState<string | null>(null);
  const stageRef = useRef<HTMLDivElement | null>(null);
  const screenRef = useRef<Screen>("login");

  useEffect(() => {
    screenRef.current = screen;
  }, [screen]);

  useEffect(() => {
    const storedName = window.localStorage.getItem("jogak_user_name");
    const storedEmail = window.localStorage.getItem("jogak_user_email");
    const storedToken = window.localStorage.getItem("jogak_access_token");
    const params = new URLSearchParams(window.location.hash.replace(/^#/, ""));
    const oauthToken = params.get("auth_token");
    const oauthName = params.get("user_name");
    const oauthEmail = params.get("user_email");

    if (oauthToken) {
      setAuthToken(oauthToken);
      if (oauthName) {
        window.localStorage.setItem("jogak_user_name", oauthName);
        setUserName(oauthName);
      }
      if (oauthEmail) {
        window.localStorage.setItem("jogak_user_email", oauthEmail);
        setUserEmail(oauthEmail);
      } else {
        window.localStorage.removeItem("jogak_user_email");
        setUserEmail("");
      }
      setLoginNotice("");
      setScreen("home");
      window.history.replaceState(null, "", window.location.pathname + window.location.search);
      return;
    }

    if (storedToken) {
      setUserName(storedName || "Google 사용자");
      setUserEmail(storedEmail || "");
      setScreen("home");
      fetchMe()
        .then((user) => {
          setUserName(user.display_name);
          setUserEmail(user.email || "");
          window.localStorage.setItem("jogak_user_name", user.display_name);
          if (user.email) {
            window.localStorage.setItem("jogak_user_email", user.email);
          } else {
            window.localStorage.removeItem("jogak_user_email");
          }
        })
        .catch(() => undefined);
    }
  }, []);

  useEffect(() => {
    const storedJobId = window.localStorage.getItem(ACTIVE_JOB_STORAGE_KEY);
    if (!storedJobId) return;
    let cancelled = false;

    fetchJob(storedJobId)
      .then((storedJob) => {
        if (cancelled) return;
        setJob(storedJob);
        setJobProgress(storedJob.progress || 0);
        if (storedJob.status === "done") {
          handleFinishedJob(storedJob);
        }
        if (storedJob.status === "failed") {
          window.localStorage.removeItem(ACTIVE_JOB_STORAGE_KEY);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setJobPollWarning("저장된 작업 상태를 다시 확인하는 중입니다.");
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const localPreviews = readSavedPreviews(userEmail);
    setSavedPreviews(localPreviews);
    if (!window.localStorage.getItem("jogak_access_token")) return;
    let cancelled = false;

    fetchFigurines()
      .then((figurines) => {
        if (cancelled) return;
        const merged = mergeSavedPreviews(localPreviews, figurines);
        setSavedPreviews(merged);
        writeSavedPreviews(userEmail, merged);
      })
      .catch(() => undefined);

    return () => {
      cancelled = true;
    };
  }, [userEmail]);

  useEffect(() => {
    fetchDestinations("")
      .then((items) => {
        setAllDestinations(items);
        if (!selectedDestination && items.length) {
          setSelectedDestination(items[0]);
        }
      })
      .catch(() => setAllDestinations([]));
  }, []);

  useEffect(() => {
    fetchDestinations(query)
      .then((items) => {
        setDestinations(items);
        if (!items.length) {
          return;
        }
        if (!selectedDestination) {
          setSelectedDestination(items[0]);
        }
      })
      .catch(() => {
        setDestinations([]);
      });
  }, [query, selectedDestination?.id]);

  useEffect(() => {
    if (!selectedDestination) {
      setPartAssets([]);
      setUnlockedParts([]);
      setLayers([]);
      setSelectedLayer("");
      setEditorSessionId(null);
      setCultureData(null);
      return;
    }
    let cancelled = false;
    setPartAssets([]);
    setUnlockedParts([]);
    setLayers([]);
    setSelectedLayer("");
    setEditorSessionId(null);
    setCultureData(null);

    fetchDestinationParts(selectedDestination.id)
      .then((parts) => {
        if (cancelled) return;
        setPartAssets(parts);
        const availableIds = initialUnlockedPartIds(parts, userEmail);
        setUnlockedParts(availableIds);
        const nextLayers = buildUnlockedLayers(parts, availableIds);
        setLayers(nextLayers);
        setSelectedLayer(nextLayers[0]?.id || "");
      })
      .catch(() => {
        if (cancelled) return;
        setPartAssets([]);
        setUnlockedParts([]);
        setLayers([]);
        setSelectedLayer("");
      });
    fetchDestinationCulture(selectedDestination.id)
      .then((nextCulture) => {
        if (!cancelled) setCultureData(nextCulture);
      })
      .catch(() => {
        if (!cancelled) setCultureData(null);
      });

    return () => {
      cancelled = true;
    };
  }, [selectedDestination?.id, userEmail]);

  useEffect(() => {
    if (!selectedDestination) {
      setPretravelConceptUrl(null);
      setCurrentFigurineId(null);
      return;
    }
    const savedPreview = savedPreviews[selectedDestination.id];
    setPretravelConceptUrl(savedPreview?.conceptUrl || null);
    setCurrentFigurineId(savedPreview?.figurineId || null);
  }, [selectedDestination?.id, savedPreviews]);

  useEffect(() => {
    if (!job?.id || ["done", "failed"].includes(job.status)) return;
    let cancelled = false;
    let failureCount = 0;

    const poll = async () => {
      try {
        const nextJob = await fetchJob(job.id);
        if (cancelled) return;
        failureCount = 0;
        setJobPollWarning("");
        setJob(nextJob);
        setJobProgress((current) => Math.max(current, nextJob.progress || 0));

        if (nextJob.status === "done") {
          handleFinishedJob(nextJob);
        }
        if (nextJob.status === "failed") {
          window.localStorage.removeItem(ACTIVE_JOB_STORAGE_KEY);
        }
      } catch {
        if (cancelled) return;
        failureCount += 1;
        setJobPollWarning(
          failureCount > 1
            ? "상태 조회가 잠시 불안정합니다. 작업은 서버에서 계속 진행됩니다."
            : "작업 상태를 다시 확인하는 중입니다."
        );
      }
    };

    poll();
    const timer = window.setInterval(poll, 3000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [job?.id, job?.status]);

  useEffect(() => {
    if (!job || ["done", "failed"].includes(job.status)) return;
    const timer = window.setInterval(() => {
      setJobProgress((current) => {
        const serverProgress = job.progress || 0;
        const floor = Math.max(current, serverProgress);
        const ceiling = estimatedProgressCeiling(job);
        if (floor >= ceiling) return floor;
        const step = job.current_state?.includes("hunyuan") ? 0.28 : 0.65;
        return Math.min(ceiling, floor + step);
      });
    }, 1400);
    return () => window.clearInterval(timer);
  }, [job?.id, job?.status, job?.progress, job?.current_state]);

  function trackJob(nextJob: JobStatus) {
    setJob(nextJob);
    setJobProgress(Math.max(nextJob.progress || 0, 4));
    setJobPollWarning("");
    setJobNotice(null);
    window.localStorage.setItem(ACTIVE_JOB_STORAGE_KEY, nextJob.id);
  }

  function rememberPreview(preview: SavedPreview) {
    setSavedPreviews((current) => {
      const next = { ...current, [preview.destinationId]: preview };
      writeSavedPreviews(userEmail, next);
      return next;
    });
  }

  function handleFinishedJob(nextJob: JobStatus) {
    const conceptUrl = typeof nextJob.result?.concept_url === "string" ? nextJob.result.concept_url : null;
    const figurineId = typeof nextJob.result?.figurine_id === "string" ? nextJob.result.figurine_id : null;
    const destinationId = typeof nextJob.result?.destination_id === "string" ? nextJob.result.destination_id : null;
    const glbUrl = typeof nextJob.result?.glb_url === "string" ? nextJob.result.glb_url : null;
    if (conceptUrl && nextJob.type === "pretravel_concept") {
      setPretravelConceptUrl(conceptUrl);
    }
    if (figurineId) {
      setCurrentFigurineId(figurineId);
    }
    if (destinationId) {
      const destination = allDestinations.find((item) => item.id === destinationId)
        || destinations.find((item) => item.id === destinationId);
      if (destination) {
        setSelectedDestination(destination);
      }
    }
    if (conceptUrl && figurineId && destinationId && nextJob.type === "pretravel_concept") {
      rememberPreview({
        destinationId,
        figurineId,
        conceptUrl,
        glbUrl,
        updatedAt: new Date().toISOString()
      });
    }

    setJob(nextJob);
    setJobProgress(100);
    setJobPollWarning("");
    window.localStorage.removeItem(ACTIVE_JOB_STORAGE_KEY);

    if (screenRef.current === "generate") {
      setScreen("preview");
      return;
    }

    const title = nextJob.type === "hunyuan_final"
      ? "최종 3D가 완성됐어요"
      : nextJob.type === "editor_refine_2d"
        ? "자연 배치 2D가 완성됐어요"
        : "방문 전 프리뷰가 완성됐어요";
    setJobNotice({
      job: nextJob,
      title,
      message: "눌러서 프리뷰를 확인하세요."
    });

    if (document.hidden && "Notification" in window && Notification.permission === "granted") {
      new Notification(title, {
        body: "조각에서 결과를 확인할 수 있습니다.",
        icon: "/icons/jogak-transparent.png"
      });
    }
  }

  function openJobNotice() {
    if (!jobNotice) return;
    setJob(jobNotice.job);
    setJobProgress(100);
    setJobNotice(null);
    setScreen("preview");
  }

  const selected = useMemo(
    () => layers.find((layer) => layer.id === selectedLayer) || null,
    [layers, selectedLayer]
  );

  async function handleGuest() {
    try {
      const session = await createGuestSession();
      setAuthToken(session.access_token);
      window.localStorage.setItem("jogak_user_name", session.user.display_name);
      window.localStorage.removeItem("jogak_user_email");
      setUserName(session.user.display_name);
      setUserEmail("");
    } catch {
      setUserName("게스트 여행자");
      setUserEmail("");
    }
    setScreen("home");
  }

  async function handleEmail() {
    if (!email.trim()) {
      setLoginNotice("이메일 주소를 입력해 주세요.");
      return;
    }
    try {
      const result = await startEmailLogin(email.trim());
      if (result.access_token && result.user) {
        setAuthToken(result.access_token);
        window.localStorage.setItem("jogak_user_name", result.user.display_name);
        if (result.user.email) {
          window.localStorage.setItem("jogak_user_email", result.user.email);
        } else {
          window.localStorage.removeItem("jogak_user_email");
        }
        setUserName(result.user.display_name);
        setUserEmail(result.user.email || "");
        setScreen("home");
      }
      setLoginNotice(result.message);
    } catch {
      setLoginNotice("백엔드 연결 전에는 게스트로 먼저 둘러볼 수 있습니다.");
    }
  }

  function handleOAuth(provider: "google" | "kakao") {
    window.location.href = `${API_BASE}/auth/oauth/${provider}`;
  }

  async function handleGenerate() {
    if (!selectedDestination) {
      setJob({ id: "missing_destination", type: "openai_concept", status: "failed", progress: 0, error: "관광지를 먼저 선택해 주세요." });
      setScreen("generate");
      return;
    }
    const form = new FormData();
    form.append("destination_id", selectedDestination.id);
    form.append("text_prompt", prompt);
    form.append("style", style);
    if (photoFile) {
      form.append("user_photo", photoFile);
    }
    try {
      const result = await createPretravelConcept(form);
      setCurrentFigurineId(result.figurine_id);
      trackJob({ id: result.job_id, type: "pretravel_concept", status: result.status, progress: 4 });
    } catch {
      setJob({ id: "create_failed", type: "pretravel_concept", status: "failed", progress: 0, error: "방문 전 프리뷰 작업을 시작하지 못했습니다." });
    }
    setJobProgress(4);
    setJobReturnScreen("maker");
    setScreen("generate");
  }

  async function handleUnlock() {
    if (!selectedDestination) {
      setUnlockNotice("관광지를 먼저 선택해 주세요.");
      return;
    }
    const applyUnlockedParts = async (unlockedPartIds: string[], message: string) => {
      const nextParts = partAssets.length ? partAssets : await fetchDestinationParts(selectedDestination.id);
      setPartAssets(nextParts);
      setUnlockedParts(unlockedPartIds);
      const nextLayers = buildUnlockedLayers(nextParts, unlockedPartIds);
      setLayers(nextLayers);
      setSelectedLayer(nextLayers[0]?.id || "");
      setUnlockNotice(message);
    };

    if (userEmail.toLowerCase() === REVIEW_UNLOCK_EMAIL) {
      try {
        setUnlockNotice("심사 계정 확인 중입니다.");
        const result = await checkVisit(selectedDestination.id, selectedDestination.lat, selectedDestination.lon, 1, true);
        if (result.verified) {
          await applyUnlockedParts(result.unlocked_parts, `${selectedDestination.name} 심사 계정으로 부품 ${result.unlocked_parts.length}개가 열렸어요.`);
          return;
        }
      } catch {
        setUnlockNotice("심사 계정 우회 확인에 실패했습니다. GPS 위치 확인으로 이어갑니다.");
      }
    }

    if (!navigator.geolocation) {
      setUnlockNotice("이 브라우저에서는 위치 확인을 사용할 수 없습니다.");
      return;
    }
    setUnlockNotice("GPS 위치를 확인하는 중입니다.");
    navigator.geolocation.getCurrentPosition(
      async (position) => {
        const { latitude, longitude, accuracy } = position.coords;
        try {
          const result = await checkVisit(selectedDestination.id, latitude, longitude, accuracy || 50);
          if (result.verified) {
            await applyUnlockedParts(result.unlocked_parts, `${selectedDestination.name} 방문이 확인됐습니다. 부품 ${result.unlocked_parts.length}개가 열렸어요.`);
          } else {
            setUnlockNotice(`아직 반경 밖입니다. 현재 약 ${Math.round(result.distance_m)}m 떨어져 있어요.`);
          }
        } catch {
          setUnlockNotice("백엔드가 꺼져 있어 위치 확인을 저장하지 못했습니다. UI는 계속 둘러볼 수 있습니다.");
        }
      },
      () => setUnlockNotice("위치 권한이 필요합니다. 브라우저 권한을 허용한 뒤 다시 확인해 주세요."),
      { enableHighAccuracy: true, timeout: 12000, maximumAge: 10000 }
    );
  }

  async function handleEditorComplete() {
    if (!selectedDestination) {
      setJob({ id: "missing_destination", type: "hunyuan_final", status: "failed", progress: 0, error: "관광지를 먼저 선택해 주세요." });
      setScreen("generate");
      return;
    }
    if (!layers.length) {
      setJob({ id: "missing_parts", type: "hunyuan_final", status: "failed", progress: 0, error: "해금된 2D 부품 이미지가 아직 없습니다. 파츠 이미지를 업로드한 뒤 다시 시도해 주세요." });
      setScreen("generate");
      return;
    }
    try {
      const session = editorSessionId
        ? { id: editorSessionId }
        : await createEditorSession(selectedDestination.id, currentFigurineId);
      setEditorSessionId(session.id);
      await patchEditorLayers(session.id, layers);
      const result = await finalizeEditor3D(session.id);
      trackJob({ id: result.job_id, type: "hunyuan_final", status: result.status, progress: 4 });
    } catch {
      setJob({ id: "editor_failed", type: "hunyuan_final", status: "failed", progress: 0, error: "편집 결과를 저장하거나 재생성 작업을 시작하지 못했습니다." });
    }
    setJobReturnScreen("editor");
    setScreen("generate");
  }

  async function handleEditorRefine2D() {
    if (!selectedDestination || !layers.length) {
      await handleEditorComplete();
      return;
    }
    try {
      const session = editorSessionId
        ? { id: editorSessionId }
        : await createEditorSession(selectedDestination.id, currentFigurineId);
      setEditorSessionId(session.id);
      await patchEditorLayers(session.id, layers);
      const result = await refineEditor2D(session.id);
      trackJob({ id: result.job_id, type: "editor_refine_2d", status: result.status, progress: 4 });
    } catch {
      setJob({ id: "editor_refine_failed", type: "editor_refine_2d", status: "failed", progress: 0, error: "자연 배치 2D 미리보기 작업을 시작하지 못했습니다." });
    }
    setJobReturnScreen("editor");
    setScreen("generate");
  }

  async function handleEditorSave() {
    if (!selectedDestination || !layers.length) return;
    const session = editorSessionId
      ? { id: editorSessionId }
      : await createEditorSession(selectedDestination.id, currentFigurineId);
    setEditorSessionId(session.id);
    await patchEditorLayers(session.id, layers);
  }

  function selectDestination(destination: Destination) {
    setSelectedDestination(destination);
    setScreen("destination");
  }

  function selectUnlockDestination(destinationId: string) {
    const destination = allDestinations.find((item) => item.id === destinationId)
      || destinations.find((item) => item.id === destinationId);
    if (!destination) return;
    setSelectedDestination(destination);
    setUnlockNotice(`${destination.name} 해금 장소를 확인합니다.`);
  }

  function handlePhotoChange(file: File | null) {
    setPhotoFile(file);
    setPhotoName(file?.name || "");
  }

  function stagePoint(event: React.PointerEvent) {
    const stage = stageRef.current?.getBoundingClientRect();
    if (!stage) return null;
    return {
      x: ((event.clientX - stage.left) / stage.width) * EDITOR_STAGE_WIDTH,
      y: ((event.clientY - stage.top) / stage.height) * EDITOR_STAGE_HEIGHT
    };
  }

  function onLayerPointerDown(event: React.PointerEvent, layer: EditorLayer) {
    const point = stagePoint(event);
    if (!point) return;
    setSelectedLayer(layer.id);
    setDragState({ id: layer.id, dx: point.x - layer.x, dy: point.y - layer.y });
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  function onStagePointerMove(event: React.PointerEvent) {
    if (!dragState) return;
    const point = stagePoint(event);
    if (!point) return;
    setLayers((items) =>
      items.map((layer) =>
        layer.id === dragState.id
          ? clampLayerPosition({ ...layer, x: point.x - dragState.dx, y: point.y - dragState.dy })
          : layer
      )
    );
  }

  function addLayer(template: EditorLayer) {
    setLayers((items) => {
      if (items.some((layer) => layer.id === template.id)) return items;
      const nextZ = Math.max(0, ...items.map((layer) => layer.z)) + 1;
      return [...items, { ...template, z: nextZ }];
    });
    setSelectedLayer(template.id);
  }

  function removeLayer(id: string) {
    const nextSelected = layers.find((layer) => layer.id !== id)?.id || "";
    setLayers((items) => items.filter((layer) => layer.id !== id));
    if (selectedLayer === id) {
      setSelectedLayer(nextSelected);
    }
  }

  function adjustLayer(update: Partial<Pick<EditorLayer, "scale" | "rotation" | "z">>) {
    setLayers((items) =>
      items.map((layer) =>
        layer.id === selectedLayer
          ? {
              ...layer,
              scale: update.scale ? clamp(layer.scale + update.scale, 0.45, 1.9) : layer.scale,
              rotation: update.rotation ? clamp(layer.rotation + update.rotation, -60, 60) : layer.rotation,
              z: update.z ? clamp(layer.z + update.z, 0, 40) : layer.z
            }
          : layer
      )
    );
  }

  function setLayerTransform(id: string, update: Partial<Pick<EditorLayer, "scale" | "rotation" | "z">>) {
    setLayers((items) =>
      items.map((layer) =>
        layer.id === id
          ? {
              ...layer,
              scale: update.scale !== undefined ? clamp(update.scale, 0.45, 1.9) : layer.scale,
              rotation: update.rotation !== undefined ? clamp(update.rotation, -60, 60) : layer.rotation,
              z: update.z !== undefined ? clamp(update.z, 0, 40) : layer.z
            }
          : layer
      )
    );
  }

  function resetSelectedLayer() {
    const current = selected;
    if (!current) return;
    const index = layers.findIndex((layer) => layer.id === current.id);
    setLayers((items) =>
      items.map((layer) =>
        layer.id === current.id
          ? {
              ...layer,
              ...defaultLayerPlacement(layer.slot, Math.max(index, 0)),
              scale: 1,
              rotation: 0
            }
          : layer
      )
    );
  }

  function openStory(from: Screen) {
    setStoryReturnScreen(from);
    setScreen("story");
  }

  const showTabs = screen !== "login";

  return (
    <main className="app-frame">
      <ServiceWorkerRegister />
      <section className={`app-phone ${screen === "login" ? "auth-mode" : ""}`}>
        {screen === "login" ? (
          <LoginScreen
            email={email}
            notice={loginNotice}
            onEmailChange={setEmail}
            onEmailStart={handleEmail}
            onGuest={handleGuest}
            onOAuth={handleOAuth}
          />
        ) : (
          <>
            <header className="app-topbar">
              <button className="brand brand-button" onClick={() => setScreen("home")} type="button" aria-label="홈으로 이동">
                <img src="/icons/jogak-transparent.png" alt="" />
                <div>
                  <span>조각</span>
                  <strong>{screenTitles[screen]}</strong>
                </div>
              </button>
            </header>

            {jobNotice && (
              <JobNoticeBanner notice={jobNotice} onOpen={openJobNotice} onDismiss={() => setJobNotice(null)} />
            )}
            {job && !["done", "failed"].includes(job.status) && screen !== "generate" && (
              <JobProgressBanner job={job} progress={jobProgress} warning={jobPollWarning} onOpen={() => setScreen("generate")} />
            )}

            <section className="screen-scroll">
              {screen === "home" && (
                <HomeScreen
                  userName={userName}
                  destination={selectedDestination}
                  onExplore={() => setScreen("explore")}
                  onMaker={() => setScreen("maker")}
                  onShipping={() => setScreen("shipping")}
                />
              )}

              {screen === "explore" && (
                <ExploreScreen
                  query={query}
                  onQuery={setQuery}
                  destinations={destinations}
                  onSelect={selectDestination}
                />
              )}

              {screen === "destination" && (
                selectedDestination ? (
                  <DestinationScreen
                    destination={selectedDestination}
                    cultureData={cultureData}
                    onBack={() => setScreen("explore")}
                    onMaker={() => setScreen("maker")}
                    onParts={() => setScreen("parts")}
                    onStory={() => openStory("destination")}
                    onRoute={() => openRoute(selectedDestination)}
                  />
                ) : (
                  <DestinationRequired onExplore={() => setScreen("explore")} />
                )
              )}

              {screen === "maker" && (
                selectedDestination ? (
                  <MakerScreen
                    destination={selectedDestination}
                    prompt={prompt}
                    style={style}
                    photoName={photoName}
                    onPhotoChange={handlePhotoChange}
                    onPrompt={setPrompt}
                    onStyle={setStyle}
                    onBack={() => setScreen("destination")}
                    onGenerate={handleGenerate}
                    onStory={() => openStory("maker")}
                  />
                ) : (
                  <DestinationRequired onExplore={() => setScreen("explore")} />
                )
              )}

              {screen === "prepreview" && (
                selectedDestination ? (
                  <PrePreviewScreen destination={selectedDestination} onUnlock={() => setScreen("unlock")} onRetry={() => setScreen("maker")} />
                ) : (
                  <DestinationRequired onExplore={() => setScreen("explore")} />
                )
              )}

              {screen === "parts" && (
                selectedDestination ? (
                  <PartsScreen
                    destination={selectedDestination}
                    parts={partAssets}
                    onBack={() => setScreen("destination")}
                    onNotify={() => setScreen("unlock")}
                    onMaker={() => setScreen("maker")}
                  />
                ) : (
                  <DestinationRequired onExplore={() => setScreen("explore")} />
                )
              )}

              {screen === "unlock" && (
                selectedDestination ? (
                  <UnlockScreen
                    destination={selectedDestination}
                    destinations={allDestinations.length ? allDestinations : destinations}
                    notice={unlockNotice}
                    unlockedParts={unlockedParts}
                    onDestinationChange={selectUnlockDestination}
                    onUnlock={handleUnlock}
                    onCustomize={() => setScreen("customize")}
                  />
                ) : (
                  <DestinationRequired onExplore={() => setScreen("explore")} />
                )
              )}

              {screen === "customize" && (
                <CustomizeScreen style={style} onStyle={setStyle} onEditor={() => setScreen("editor")} />
              )}

              {screen === "generate" && (
                <GenerateScreen progress={jobProgress} job={job} warning={jobPollWarning} onLeave={() => setScreen(jobReturnScreen)} />
              )}

              {screen === "editor" && (
                <EditorScreen
                  layers={layers}
                  selected={selected}
                  availableLayers={buildUnlockedLayers(partAssets, unlockedParts)}
                  destination={selectedDestination}
                  basePreviewUrl={pretravelConceptUrl || resultString(job, "concept_url") || null}
                  stageRef={stageRef}
                  onPointerMove={onStagePointerMove}
                  onPointerUp={() => setDragState(null)}
                  onLayerPointerDown={onLayerPointerDown}
                  onSelect={setSelectedLayer}
                  onAddLayer={addLayer}
                  onRemoveLayer={removeLayer}
                  onAdjust={adjustLayer}
                  onSetLayer={setLayerTransform}
                  onReset={resetSelectedLayer}
                  onSave={handleEditorSave}
                  onRefine={handleEditorRefine2D}
                  onComplete={handleEditorComplete}
                />
              )}

              {screen === "preview" && (
                selectedDestination ? (
                  <PreviewScreen
                    destination={selectedDestination}
                    job={job}
                    savedPreview={savedPreviews[selectedDestination.id] || null}
                    onPrint={() => setScreen("print")}
                    onEdit={() => setScreen("editor")}
                    onStory={() => openStory("preview")}
                  />
                ) : (
                  <DestinationRequired onExplore={() => setScreen("explore")} />
                )
              )}

              {screen === "story" && (
                selectedDestination ? (
                  <StoryScreen
                    destination={selectedDestination}
                    cultureData={cultureData}
                    parts={partAssets}
                    onBack={() => setScreen(storyReturnScreen)}
                  />
                ) : <DestinationRequired onExplore={() => setScreen("explore")} />
              )}

              {screen === "print" && (
                selectedDestination ? (
                  <PrintScreen destination={selectedDestination} onBack={() => setScreen("preview")} onShipping={() => setScreen("shipping")} />
                ) : (
                  <DestinationRequired onExplore={() => setScreen("explore")} />
                )
              )}

              {screen === "shipping" && <ShippingScreen onHome={() => setScreen("home")} />}

              {screen === "profile" && (
                <ProfileScreen userName={userName} onLogin={() => setScreen("login")} />
              )}
            </section>

            {showTabs && <TabBar active={screen} onNavigate={setScreen} />}
          </>
        )}
      </section>
    </main>
  );
}

function LoginScreen({
  email,
  notice,
  onEmailChange,
  onEmailStart,
  onGuest,
  onOAuth
}: {
  email: string;
  notice: string;
  onEmailChange: (value: string) => void;
  onEmailStart: () => void;
  onGuest: () => void;
  onOAuth: (provider: "google" | "kakao") => void;
}) {
  return (
    <div className="login-screen">
      <img className="hero-logo" src="/icons/jogak-transparent.png" alt="조각" />
      <h1>조각</h1>
      <p>여행지를 사진이 아니라 손에 잡히는 조각으로 남겨보세요.</p>

      <label className="field-label" htmlFor="email">
        이메일
      </label>
      <input id="email" className="text-input" value={email} onChange={(event) => onEmailChange(event.target.value)} placeholder="you@example.com" inputMode="email" />
      <div className="button-stack">
        <button className="primary" onClick={onEmailStart} type="button">
          <Mail aria-hidden />
          이메일로 시작하기
        </button>
        <button className="secondary google" onClick={() => onOAuth("google")} type="button">
          <GoogleLogo />
          Google로 계속하기
        </button>
        <button className="secondary kakao" onClick={() => onOAuth("kakao")} type="button">
          <span className="kakao-logo">k</span>
          Kakao로 계속하기
        </button>
        <button className="secondary" onClick={onGuest} type="button">
          <Eye aria-hidden />
          게스트로 둘러보기
        </button>
      </div>
      <p className="data-note">{notice || "로그인하면 여행 기록, 만든 조각, 제작 요청, 배송 상태가 내 조각장에 저장됩니다."}</p>
    </div>
  );
}

function DestinationRequired({ onExplore }: { onExplore: () => void }) {
  return (
    <div className="screen-section">
      <h1 className="title-tight">관광지를 먼저 선택해 주세요</h1>
      <p className="desc">백엔드에서 불러온 관광지 데이터가 있어야 생성, 해금, 제작 흐름을 시작할 수 있습니다.</p>
      <div className="button-stack">
        <button className="primary" onClick={onExplore} type="button">
          <Compass aria-hidden />
          관광지 탐색하기
        </button>
      </div>
    </div>
  );
}

function HomeScreen({
  userName,
  destination,
  onExplore,
  onMaker,
  onShipping
}: {
  userName: string;
  destination: Destination | null;
  onExplore: () => void;
  onMaker: () => void;
  onShipping: () => void;
}) {
  return (
    <div className="screen-section">
      <div className="screen-heading">
        <h1>나의 조각장</h1>
        <button className="icon-text" type="button">
          <Bell aria-hidden />
          알림
        </button>
      </div>
      <p className="desc">{userName ? `${userName}의 여행 조각이 쌓이고 있어요.` : "여행할 때마다 장소의 기억이 피규어로 쌓입니다."}</p>
      <div className="metrics">
        <div>
          <b>0</b>
          <span>보유 조각</span>
        </div>
        <div>
          <b>0</b>
          <span>제작 가능</span>
        </div>
        <div>
          <b>0</b>
          <span>배송 중</span>
        </div>
      </div>
      <div className="label">오늘 할 수 있는 일</div>
      <div className="action-list">
        <ActionRow icon={<MapPin />} title="근처 해금 장소 찾기" text={destination ? `현재 선택 장소: ${destination.name}` : "관광지를 먼저 선택해 주세요."} tag="GPS" onClick={onExplore} />
        <ActionRow icon={<ImagePlus />} title="여행 전 조각 만들기" text="내 사진과 텍스트로 먼저 조각을 만들어봅니다." tag="PRE" onClick={onMaker} />
        <ActionRow icon={<Truck />} title="배송 상태 확인" text="제작소에 맡긴 조각의 진행 상황을 봅니다." tag="LIVE" onClick={onShipping} />
      </div>
      <div className="button-stack">
        <button className="primary" onClick={onExplore} type="button">
          <Compass aria-hidden />
          주변 장소 보기
        </button>
        <button className="secondary" onClick={onMaker} type="button">
          <ImagePlus aria-hidden />
          방문 전 조각 만들기
        </button>
      </div>
    </div>
  );
}

function ExploreScreen({
  query,
  onQuery,
  destinations,
  onSelect
}: {
  query: string;
  onQuery: (value: string) => void;
  destinations: Destination[];
  onSelect: (destination: Destination) => void;
}) {
  return (
    <div className="screen-section">
      <div className="screen-heading">
        <h1>어디를 조각할까요?</h1>
        <button className="icon-text" type="button">
          <Map aria-hidden />
          지도
        </button>
      </div>
      <p className="desc">관광지를 고르면 만들 수 있는 조각, 해금 부품, 장소 이야기를 먼저 볼 수 있습니다.</p>
      <label className="search-box">
        <Search aria-hidden />
        <input value={query} onChange={(event) => onQuery(event.target.value)} placeholder="관광지, 지역, 문화유산 검색" />
      </label>
      <div className="chips">
        {["전체", "박물관", "궁궐", "한옥", "축제", "시장"].map((chip, index) => (
          <button className={`chip ${index === 0 ? "active" : ""}`} type="button" key={chip}>
            {chip}
          </button>
        ))}
      </div>
      <div className="label">추천 관광지</div>
      <div className="action-list">
        {destinations.length ? (
          destinations.map((destination) => (
            <ActionRow
              key={destination.id}
              icon={<Landmark />}
              title={destination.name}
              text={`${destination.dna} · ${destination.parts.length}개 부품`}
              tag={destination.region}
              onClick={() => onSelect(destination)}
            />
          ))
        ) : (
          <ActionRow icon={<Landmark />} title="불러온 관광지가 없습니다" text="관광지 목록을 다시 불러와 주세요." tag="EMPTY" />
        )}
      </div>
    </div>
  );
}

function DestinationScreen({
  destination,
  cultureData,
  onBack,
  onMaker,
  onParts,
  onStory,
  onRoute
}: {
  destination: Destination;
  cultureData: DestinationCulture | null;
  onBack: () => void;
  onMaker: () => void;
  onParts: () => void;
  onStory: () => void;
  onRoute: () => void;
}) {
  return (
    <div className="screen-section">
      <div className="screen-heading">
        <button className="icon-text" onClick={onBack} type="button">
          <ChevronLeft aria-hidden />
          탐색
        </button>
        <button className="icon-text" type="button">
          <Share2 aria-hidden />
          공유
        </button>
      </div>
      <h1 className="title-tight">{destination.name}</h1>
      <p className="desc">{destination.summary}</p>
      {destination.representative_image_url && (
        <img className="destination-photo" src={destination.representative_image_url} alt={`${destination.name} 대표 이미지`} />
      )}
      <div className="map-panel">
        <iframe
          title={`${destination.name} 지도`}
          src={`https://www.openstreetmap.org/export/embed.html?bbox=${destination.lon - 0.01}%2C${destination.lat - 0.01}%2C${destination.lon + 0.01}%2C${destination.lat + 0.01}&layer=mapnik&marker=${destination.lat}%2C${destination.lon}`}
          loading="lazy"
        />
      </div>
      <div className="label">이곳에서 만나는 것</div>
      <div className="action-list">
        <ActionRow icon={<BookOpen />} title="대표 이야기" text={destination.dna} tag="STORY" onClick={onStory} />
        <ActionRow
          icon={<ImageIcon />}
          title="관광지 자료"
          text={
            cultureData?.destination_sources.length
              ? `${destination.name}에 대한 이야기 ${cultureData.destination_sources.length}건이 연결됐습니다.`
              : "관광지 자료를 불러오면 대표 이야기와 이미지가 연결됩니다."
          }
          tag={cultureData?.destination_sources.length ? "연결됨" : "대기"}
        />
        <ActionRow icon={<Route />} title="가는 길" text="실제 지도 좌표를 기준으로 이동 경로를 엽니다." tag="MAP" onClick={onRoute} />
      </div>
      <div className="button-stack">
        <button className="primary" onClick={onMaker} type="button">
          <ImagePlus aria-hidden />
          방문 전 조각 만들기
        </button>
        <button className="secondary" onClick={onRoute} type="button">
          <MapPin aria-hidden />
          이 장소로 길찾기
        </button>
        <button className="secondary" onClick={onParts} type="button">
          <Sparkles aria-hidden />
          만들 수 있는 조각 보기
        </button>
      </div>
    </div>
  );
}

function MakerScreen({
  destination,
  prompt,
  style,
  photoName,
  onPhotoChange,
  onPrompt,
  onStyle,
  onBack,
  onGenerate,
  onStory
}: {
  destination: Destination;
  prompt: string;
  style: string;
  photoName: string;
  onPhotoChange: (file: File | null) => void;
  onPrompt: (value: string) => void;
  onStyle: (value: string) => void;
  onBack: () => void;
  onGenerate: () => void;
  onStory: () => void;
}) {
  return (
    <div className="screen-section">
      <div className="screen-heading">
        <button className="icon-text" onClick={onBack} type="button">
          <ChevronLeft aria-hidden />
          장소
        </button>
      </div>
      <h1 className="title-tight">가기 전에 먼저 만들어보기</h1>
      <p className="desc">내 사진과 한 줄 설명으로 기본 조각을 먼저 만들어요. 해금 부품과 읽히는 글씨는 방문 전 이미지에 들어가지 않습니다.</p>
      <div className="upload-zone">
        <div className="portrait" />
        <div>
          <b>내 사진 추가</b>
          <span>{photoName || "피규어에 어울리는 인상만 가볍게 반영합니다."}</span>
          <label className="ghost file-pick">
            <Camera aria-hidden />
            사진 선택
            <input type="file" accept="image/png,image/jpeg,image/webp" onChange={(event) => onPhotoChange(event.target.files?.[0] || null)} />
          </label>
        </div>
      </div>
      <label className="field-label" htmlFor="prompt">
        어떤 느낌이면 좋나요?
      </label>
      <textarea id="prompt" className="textarea" value={prompt} onChange={(event) => onPrompt(event.target.value)} />
      <div className="label">형태</div>
      <div className="chips">
        {["책상 피규어", "키링", "자석", "디오라마"].map((item) => (
          <button className={`chip ${style === item ? "active" : ""}`} key={item} onClick={() => onStyle(item)} type="button">
            {item}
          </button>
        ))}
      </div>
      <div className="label">방문 후 열리는 부품</div>
      <div className="chips">
        {destination.parts.slice(0, 4).map((part, index) => (
          <button className="chip" key={part} type="button">
            {index === 0 && <Gem aria-hidden />}
            {index === 1 && <Crown aria-hidden />}
            {index === 2 && <Landmark aria-hidden />}
            {part.replace(/ (base|head|pattern|prop|cape|texture|pose|tag)$/i, "")}
          </button>
        ))}
      </div>
      <div className="button-stack">
        <button className="primary" onClick={onGenerate} type="button">
          <WandSparkles aria-hidden />
          방문 전 조각 생성
        </button>
        <button className="secondary" onClick={onStory} type="button">
          <BookOpen aria-hidden />
          관광지 이야기 더 보기
        </button>
      </div>
    </div>
  );
}

function PrePreviewScreen({ destination, onUnlock, onRetry }: { destination: Destination; onUnlock: () => void; onRetry: () => void }) {
  return (
    <div className="screen-section">
      <h1 className="title-tight">방문 전 조각이 나왔어요</h1>
      <p className="desc">이 조각은 미리보기입니다. 실제 장소에 도착하면 잠긴 부품이 열리고 더 완성도 있게 다듬을 수 있어요.</p>
      <div className="pre-figure">
        <div className="ghost-sculpt" />
      </div>
      <div className="label">미리 담긴 요소</div>
      <div className="action-list">
        <ActionRow icon={<ImageIcon />} title="내 사진의 인상" text="헤어와 분위기만 피규어 스타일로 반영했습니다." tag="반영" />
        <ActionRow icon={<Landmark />} title={destination.name} text={destination.dna} tag="장소" />
        <ActionRow icon={<Unlock />} title="잠긴 부품" text="현장에 도착하면 10개 부품이 열립니다." tag="해금" />
      </div>
      <div className="button-stack">
        <button className="primary" onClick={onUnlock} type="button">
          <MapPin aria-hidden />
          현장 도착하면 완성하기
        </button>
        <button className="secondary" onClick={onRetry} type="button">
          <RefreshCw aria-hidden />
          다시 만들어보기
        </button>
      </div>
    </div>
  );
}

function PartsScreen({
  destination,
  parts,
  onBack,
  onNotify,
  onMaker
}: {
  destination: Destination;
  parts: PartAsset[];
  onBack: () => void;
  onNotify: () => void;
  onMaker: () => void;
}) {
  return (
    <div className="screen-section">
      <div className="screen-heading">
        <button className="icon-text" onClick={onBack} type="button">
          <ChevronLeft aria-hidden />
          장소
        </button>
        <button className="icon-text" type="button">
          <Bookmark aria-hidden />
          담기
        </button>
      </div>
      <h1 className="title-tight">이곳에서 만들 수 있는 조각</h1>
      <p className="desc">부품은 이미 제작되어 있으며, 각 부품에는 실제 문화유산과 전시 이야기가 연결됩니다.</p>
      <div className="label">해금 가능한 부품 {parts.length || destination.parts.length}</div>
      <div className="part-catalog">
        {parts.length ? parts.map((part) => {
          const source = part.public_sources[0];
          return (
            <article className="part-catalog-row" key={part.id}>
              {part.image_url ? <img src={part.image_url} alt="" /> : <div className="part-image-empty" />}
              <div>
                <b>{part.name}</b>
                <span>{source ? sourceFact(source) : "문화유산 이야기 연결 대기"}</span>
                {part.limited && (
                  <em>{part.limited_available ? "현재 전시 한정 해금 가능" : "전시 기간 외 잠김"}</em>
                )}
              </div>
              <small>{source ? "이야기" : part.slot.toUpperCase()}</small>
            </article>
          );
        }) : destination.parts.map((part) => (
          <article className="part-catalog-row" key={part}>
            <div className="part-image-empty" />
            <div>
              <b>{part}</b>
              <span>부품 메타데이터를 불러오는 중입니다.</span>
            </div>
          </article>
        ))}
      </div>
      <div className="button-stack">
        <button className="primary" onClick={onNotify} type="button">
          <MapPin aria-hidden />
          현장 도착하면 알림 받기
        </button>
        <button className="secondary" onClick={onMaker} type="button">
          <Palette aria-hidden />
          내 스타일 먼저 정하기
        </button>
      </div>
    </div>
  );
}

function UnlockScreen({
  destination,
  destinations,
  notice,
  unlockedParts,
  onDestinationChange,
  onUnlock,
  onCustomize
}: {
  destination: Destination;
  destinations: Destination[];
  notice: string;
  unlockedParts: string[];
  onDestinationChange: (destinationId: string) => void;
  onUnlock: () => void;
  onCustomize: () => void;
}) {
  return (
    <div className="screen-section">
      <div className="screen-heading">
        <h1>도착했어요. 조각을 열까요?</h1>
        <button className="icon-text" onClick={onUnlock} type="button">
          <LocateFixed aria-hidden />
          위치
        </button>
      </div>
      <p className="desc">{notice}</p>
      <label className="select-row">
        <span>해금 장소</span>
        <select value={destination.id} onChange={(event) => onDestinationChange(event.target.value)}>
          {destinations.map((item) => (
            <option key={item.id} value={item.id}>{item.name}</option>
          ))}
        </select>
      </label>
      <div className="map-panel compact">
        <iframe
          title={`${destination.name} 해금 지도`}
          src={`https://www.openstreetmap.org/export/embed.html?bbox=${destination.lon - 0.006}%2C${destination.lat - 0.006}%2C${destination.lon + 0.006}%2C${destination.lat + 0.006}&layer=mapnik&marker=${destination.lat}%2C${destination.lon}`}
          loading="lazy"
        />
      </div>
      <div className="progress-list unlock-progress">
        <Step done title="장소 좌표 준비" text={`${destination.name} geofence 반경 ${destination.radius_m}m`} tag="확인" />
        <Step done={unlockedParts.length > 0} now={unlockedParts.length === 0} title="GPS 방문 확인" text="위치 정확도와 체류 시간을 함께 저장합니다." tag={unlockedParts.length ? "완료" : "진행"} />
        <Step done={unlockedParts.length > 0} title="부품 해금" text={`${destination.parts.length}개 부품으로 조각 생성 가능`} tag="대기" />
      </div>
      <div className="button-stack">
        <button className="primary" onClick={onUnlock} type="button">
          <Unlock aria-hidden />
          이 장소 조각 열기
        </button>
        <button className="secondary" onClick={onCustomize} type="button">
          <Sparkles aria-hidden />
          해금 후 조각 만들기
        </button>
      </div>
    </div>
  );
}

function CustomizeScreen({ style, onStyle, onEditor }: { style: string; onStyle: (value: string) => void; onEditor: () => void }) {
  return (
    <div className="screen-section">
      <h1 className="title-tight">해금된 조각을 어디에 둘까요?</h1>
      <p className="desc">방문 전 프리뷰 위에 부품을 올려 배치하면, 서버가 위치 관계를 해석해 최종 2D와 3D를 만듭니다.</p>
      <div className="label">형태 선택</div>
      <div className="chips">
        {["책상 피규어", "키링", "자석", "디오라마"].map((item) => (
          <button className={`chip ${style === item ? "active" : ""}`} key={item} onClick={() => onStyle(item)} type="button">
            {item}
          </button>
        ))}
      </div>
      <div className="label">스타일</div>
      <div className="action-list profile-actions">
        <ActionRow icon={<Move />} title="드래그 배치" text="원하는 위치로 옮기면 최종 3D 조립 좌표로 저장됩니다." tag="LAYOUT" />
        <ActionRow icon={<RotateCw />} title="회전과 크기" text="부품 모양은 유지하고, 방향과 비율만 조절합니다." tag="PART" />
        <ActionRow icon={<PackageCheck />} title="출력 안정형" text="베이스, 건물, 손소품, 머리장식을 각기 다른 규칙으로 조립합니다." tag="3D" />
      </div>
      <div className="button-stack">
        <button className="primary" onClick={onEditor} type="button">
          <Move aria-hidden />
          프리뷰 위에 부품 배치하기
        </button>
      </div>
    </div>
  );
}

function JobProgressBanner({
  job,
  progress,
  warning,
  onOpen
}: {
  job: JobStatus;
  progress: number;
  warning: string;
  onOpen: () => void;
}) {
  const roundedProgress = Math.max(0, Math.min(100, Math.round(progress)));
  return (
    <button className="job-banner running" onClick={onOpen} type="button">
      <Bell aria-hidden />
      <span>
        <b>{jobStatusLabel(job)}</b>
        <small>{warning || `${roundedProgress}% 진행 중 · 눌러서 작업 화면 보기`}</small>
      </span>
      <em>{roundedProgress}%</em>
    </button>
  );
}

function JobNoticeBanner({
  notice,
  onOpen,
  onDismiss
}: {
  notice: JobNotice;
  onOpen: () => void;
  onDismiss: () => void;
}) {
  return (
    <div className="job-banner done">
      <button className="job-banner-main" onClick={onOpen} type="button">
        <Check aria-hidden />
        <span>
          <b>{notice.title}</b>
          <small>{notice.message}</small>
        </span>
      </button>
      <button className="job-banner-close" onClick={onDismiss} type="button" aria-label="알림 닫기">
        <X aria-hidden />
      </button>
    </div>
  );
}

function GenerateScreen({
  progress,
  job,
  warning,
  onLeave
}: {
  progress: number;
  job: JobStatus | null;
  warning: string;
  onLeave: () => void;
}) {
  const failed = job?.status === "failed";
  const isFinal = job?.type === "hunyuan_final";
  const isRefine = job?.type === "editor_refine_2d";
  const roundedProgress = Math.max(0, Math.min(100, Math.round(progress)));
  return (
    <div className="screen-section">
      <div className="screen-heading">
        <h1>{isFinal ? "최종 3D를 조립하고 있어요" : isRefine ? "배치 이미지를 정리하고 있어요" : "방문 전 프리뷰를 만들고 있어요"}</h1>
        <button className="icon-text" onClick={onLeave} type="button">
          <X aria-hidden />
          나중에 보기
        </button>
      </div>
      <p className="desc">
        {failed
          ? job?.error || "생성 작업이 실패했습니다."
          : isFinal
            ? "배치한 부품의 형태를 보존하면서 캐릭터와 부품을 따로 입체화한 뒤 하나의 조각으로 맞춥니다."
            : isRefine
              ? "프리뷰와 해금 부품의 배치 의도를 보존해 자연스러운 2D 확인 이미지를 만듭니다."
              : "해금 부품은 넣지 않고, 의상과 원판, 장소 분위기만 반영한 방문 전 2D/3D 프리뷰를 만듭니다."}
      </p>
      <div className="progress-meter">
        <span style={{ width: `${roundedProgress}%` }} />
      </div>
      <div className="job-status-line">
        <b>{roundedProgress}%</b>
        <span>{jobStatusLabel(job)}</span>
      </div>
      {warning && <p className="job-warning">{warning}</p>}
      <div className="progress-list">
        <Step done={progress > 24} now={progress <= 24} title="문화 DNA 정리" text="장소 특색과 사용자 입력을 합칩니다." tag="DNA" />
        <Step
          done={progress > 52}
          now={progress > 24 && progress <= 52}
          title={isFinal ? "최종 2D 배치 확인" : "2D 프리뷰"}
          text={isFinal ? "부품 모양을 유지하며 착용, 손, 배경, 베이스 관계를 정리합니다." : "장소 분위기와 인물 사진을 바탕으로 3D에 잘 맞는 입력 이미지를 만듭니다."}
          tag="2D"
        />
        <Step
          done={progress > 82}
          now={progress > 52 && progress <= 82}
          title={isFinal ? "부품 입체화" : "3D 프리뷰 변환"}
          text={isFinal ? "캐릭터와 각 부품을 따로 입체화해 원래 형태를 최대한 보존합니다." : "방문 전 조각을 3D 미리보기로 변환합니다."}
          tag="3D"
        />
        <Step
          done={progress >= 100}
          now={progress > 82 && progress < 100}
          title={isFinal ? "최종 조립" : "제작 파일 준비"}
          text={isFinal ? "원판, 발 접지, 착용 부품, 손소품, 배경 요소를 하나의 피규어로 맞춥니다." : "후처리와 출력 안정성 확인을 준비합니다."}
          tag="STL"
        />
      </div>
      <p className="data-note">작업 번호 {job?.id || "local"} · 화면을 나가도 제작은 계속됩니다.</p>
    </div>
  );
}

function EditorScreen({
  layers,
  selected,
  availableLayers,
  destination,
  basePreviewUrl,
  stageRef,
  onPointerMove,
  onPointerUp,
  onLayerPointerDown,
  onSelect,
  onAddLayer,
  onRemoveLayer,
  onAdjust,
  onSetLayer,
  onReset,
  onSave,
  onRefine,
  onComplete
}: {
  layers: EditorLayer[];
  selected: EditorLayer | null;
  availableLayers: EditorLayer[];
  destination: Destination | null;
  basePreviewUrl: string | null;
  stageRef: React.RefObject<HTMLDivElement | null>;
  onPointerMove: (event: React.PointerEvent) => void;
  onPointerUp: () => void;
  onLayerPointerDown: (event: React.PointerEvent, layer: EditorLayer) => void;
  onSelect: (id: string) => void;
  onAddLayer: (layer: EditorLayer) => void;
  onRemoveLayer: (id: string) => void;
  onAdjust: (update: Partial<Pick<EditorLayer, "scale" | "rotation" | "z">>) => void;
  onSetLayer: (id: string, update: Partial<Pick<EditorLayer, "scale" | "rotation" | "z">>) => void;
  onReset: () => void;
  onSave: () => void;
  onRefine: () => void;
  onComplete: () => void;
}) {
  const selectedSize = selected ? layerSize(selected.slot) : { width: 72, height: 72 };
  const placedIds = new Set(layers.map((layer) => layer.id));
  return (
    <div className="screen-section editor-workflow">
      <div className="screen-heading">
        <div>
          <h1>프리뷰 위에 부품 배치</h1>
          <p className="section-kicker">{destination?.name || "선택한 장소"} · {layers.length}/{availableLayers.length}개 사용 중</p>
        </div>
        <button className="icon-text" onClick={onSave} type="button">
          <Save aria-hidden />
          저장
        </button>
      </div>
      <p className="desc">위치, 크기, 회전, 앞뒤 순서가 최종 3D 조립 좌표로 저장됩니다.</p>

      <div className="editor-layout">
        <section className="editor-canvas-panel" aria-label="부품 배치 작업대">
          <div className="edit-stage-shell">
            <div className="edit-stage" ref={stageRef} onPointerMove={onPointerMove} onPointerUp={onPointerUp} onPointerLeave={onPointerUp}>
              {basePreviewUrl ? (
                <img className="editor-base-preview" src={basePreviewUrl} alt="" draggable={false} />
              ) : (
                <div className="editor-base-placeholder">
                  <ImageIcon aria-hidden />
                  <span>방문 전 프리뷰가 여기에 놓입니다</span>
                </div>
              )}
              <div className="stage-safe-area" aria-hidden />
              {layers.length ? (
                layers
                  .slice()
                  .sort((a, b) => a.z - b.z)
                  .map((layer) => {
                    const size = layerSize(layer.slot);
                    return (
                      <button
                        className={`layer layer-${layer.slot} ${selected?.id === layer.id ? "selected" : ""}`}
                        key={layer.id}
                        style={{
                          left: layer.x,
                          top: layer.y,
                          width: size.width,
                          height: size.height,
                          transform: `rotate(${layer.rotation}deg) scale(${layer.scale})`,
                          zIndex: layer.z,
                          backgroundColor: layer.imageUrl ? "transparent" : layer.color
                        }}
                        onPointerDown={(event) => onLayerPointerDown(event, layer)}
                        onClick={() => onSelect(layer.id)}
                        type="button"
                        aria-label={layer.label}
                      >
                        {layer.imageUrl && <img src={layer.imageUrl} alt="" draggable={false} />}
                      </button>
                    );
                  })
              ) : (
                <div className="empty-stage">{availableLayers.length ? "아래 트레이에서 사용할 부품을 추가하세요." : "해금된 2D 부품 이미지가 아직 없습니다."}</div>
              )}
            </div>
          </div>

          <div className="editor-toolbar" aria-label="편집 도구">
            <button className="tool-btn active" type="button" title="드래그">
              <Move aria-hidden />
            </button>
            <button className="tool-btn" onClick={() => onAdjust({ rotation: -8 })} type="button" title="왼쪽 회전">
              <RotateCcw aria-hidden />
            </button>
            <button className="tool-btn" onClick={() => onAdjust({ rotation: 8 })} type="button" title="오른쪽 회전">
              <RotateCw aria-hidden />
            </button>
            <button className="tool-btn" onClick={() => onAdjust({ scale: 0.08 })} type="button" title="크게">
              <Maximize2 aria-hidden />
            </button>
            <button className="tool-btn" onClick={onReset} type="button" title="위치 초기화">
              <Undo2 aria-hidden />
            </button>
          </div>
        </section>

        <aside className="editor-side-panel">
          <div className="part-tray" aria-label="해금 부품">
            {availableLayers.map((layer) => {
              const placed = placedIds.has(layer.id);
              return (
              <button
                className={`tray-part ${selected?.id === layer.id ? "active" : ""} ${placed ? "placed" : ""}`}
                key={layer.id}
                onClick={() => placed ? onSelect(layer.id) : onAddLayer(layer)}
                type="button"
              >
                {layer.imageUrl ? <img src={layer.imageUrl} alt="" draggable={false} /> : <span />}
                <b>{layer.label}</b>
                <small>{placed ? "사용 중" : "추가"}</small>
              </button>
              );
            })}
          </div>

          {selected ? (
            <div className="selected-editor">
              <div className="selected-head">
                <div>
                  <span>선택된 부품</span>
                  <strong>{selected.label}</strong>
                </div>
                <em>{modeLabel(selected.slot)}</em>
              </div>
              <button className="remove-part-btn" onClick={() => onRemoveLayer(selected.id)} type="button">
                <Trash2 aria-hidden />
                이 부품 빼기
              </button>
              <label className="range-row">
                <span>크기</span>
                <input min="0.45" max="1.9" step="0.01" type="range" value={selected.scale} onChange={(event) => onSetLayer(selected.id, { scale: Number(event.target.value) })} />
                <b>{Math.round(selected.scale * 100)}%</b>
              </label>
              <label className="range-row">
                <span>회전</span>
                <input min="-60" max="60" step="1" type="range" value={selected.rotation} onChange={(event) => onSetLayer(selected.id, { rotation: Number(event.target.value) })} />
                <b>{Math.round(selected.rotation)}°</b>
              </label>
              <div className="nudge-grid">
                <button className="secondary-mini" onClick={() => onAdjust({ z: -1 })} type="button">뒤로</button>
                <button className="secondary-mini" onClick={() => onAdjust({ z: 1 })} type="button">앞으로</button>
                <button className="secondary-mini" onClick={() => onAdjust({ scale: -0.06 })} type="button">작게</button>
                <button className="secondary-mini" onClick={() => onAdjust({ scale: 0.06 })} type="button">크게</button>
              </div>
              <p className="data-note">{selectedSize.width}×{selectedSize.height} 작업대 단위 · 이 배치는 Blender 조립 manifest에 그대로 저장됩니다.</p>
            </div>
          ) : (
            <div className="selected-editor empty-selection">
              <b>부품을 선택해 주세요</b>
              <span>아래 부품 트레이나 작업대 위 이미지를 누르면 세부 조절이 열립니다.</span>
            </div>
          )}

          <div className="pipeline-note">
            <Step done title="2D 배치" text="사용자가 놓은 위치, 크기, 회전, 앞뒤 순서를 저장합니다." tag="NOW" />
            <Step title="자연 배치 이미지" text="부품 모양은 유지하고 착용/손/배경 관계를 정리합니다." tag="2D" />
            <Step title="부품별 3D 조립" text="Hunyuan과 Blender가 발 접지와 베이스를 맞춥니다." tag="3D" />
          </div>

          <div className="button-stack">
            <button className="primary" onClick={onComplete} type="button">
              <Check aria-hidden />
              최종 3D 만들기
            </button>
            <button className="secondary" onClick={onRefine} type="button">
              <ImageIcon aria-hidden />
              자연 배치 2D만 먼저 보기
            </button>
          </div>
        </aside>
      </div>
    </div>
  );
}

function resultString(job: JobStatus | null, key: string): string | undefined {
  const value = job?.result?.[key];
  return typeof value === "string" ? value : undefined;
}

function PreviewScreen({
  destination,
  job,
  savedPreview,
  onPrint,
  onEdit,
  onStory
}: {
  destination: Destination;
  job: JobStatus | null;
  savedPreview: SavedPreview | null;
  onPrint: () => void;
  onEdit: () => void;
  onStory: () => void;
}) {
  const conceptUrl = resultString(job, "concept_url") || savedPreview?.conceptUrl;
  const glbUrl = resultString(job, "glb_url") || savedPreview?.glbUrl || undefined;

  return (
    <div className="screen-section">
      <div className="screen-heading">
        <h1>{destination.name} 조각 완성</h1>
        <button className="icon-text" type="button">
          <Heart aria-hidden />
          저장
        </button>
      </div>
      <p className="desc">화면에서는 색과 질감을 볼 수 있고, 제작소에는 출력용 파일이 함께 전달됩니다.</p>
      {conceptUrl && <img className="concept-preview" src={conceptUrl} alt={`${destination.name} 2D 컨셉`} />}
      <ModelViewer src={glbUrl} />
      <div className="chips">
        <button className="chip active" type="button">
          <Rotate3D aria-hidden />
          회전
        </button>
        <button className="chip" type="button">확대</button>
        <button className="chip" type="button">색 보기</button>
        <button className="chip" type="button">AR</button>
      </div>
      <div className="button-stack">
        <button className="primary" onClick={onPrint} type="button">
          <PackageCheck aria-hidden />
          제작 파일 준비하기
        </button>
        <button className="secondary" onClick={onEdit} type="button">
          <Move aria-hidden />
          조금 더 다듬기
        </button>
        <button className="secondary" onClick={onStory} type="button">
          <BookOpen aria-hidden />
          조각 이야기 보기
        </button>
      </div>
    </div>
  );
}

function StoryScreen({
  destination,
  cultureData,
  parts,
  onBack
}: {
  destination: Destination;
  cultureData: DestinationCulture | null;
  parts: PartAsset[];
  onBack: () => void;
}) {
  const sourcedParts = parts.filter((part) => part.public_sources.length);
  const officialUrl = officialDestinationUrl(destination, cultureData, sourcedParts);
  const storyCount = sourcedParts.reduce((total, part) => total + part.public_sources.length, 0);
  return (
    <div className="screen-section">
      <div className="screen-heading">
        <button className="icon-text" onClick={onBack} type="button">
          <ChevronLeft aria-hidden />
          돌아가기
        </button>
        <button className="icon-text" type="button">
          <Flag aria-hidden />
          신고
        </button>
      </div>
      <h1 className="title-tight">{destination.name} 이야기</h1>
      <div className="action-list">
        <ActionRow icon={<Gem />} title="이곳의 분위기" text={destination.dna} tag="장소" />
        <ActionRow
          icon={<BookOpen />}
          title="조각에 담긴 소재"
          text={heritagePartSummary(sourcedParts, destination)}
          tag={`${storyCount}개`}
        />
        <ActionRow
          icon={<ImageIcon />}
          title="여행 후 열리는 이야기"
          text="해금된 부품을 누르면 실제 유물, 시대, 소재와 연결된 짧은 해설을 함께 볼 수 있습니다."
          tag="해금"
        />
      </div>
      <div className="label">부품별 문화유산 이야기</div>
      <div className="source-list">
        {sourcedParts.length ? sourcedParts.map((part) => (
          <section className="provenance-part" key={part.id}>
            <div className="provenance-heading">
              {part.image_url && <img src={part.image_url} alt="" />}
              <div>
                <b>{part.name}</b>
                <span>{part.public_sources.length}개의 문화유산 이야기</span>
              </div>
            </div>
            {part.public_sources.map((source) => (
              <PublicSourceRow key={`${part.id}-${source.id}`} source={source} />
            ))}
          </section>
        )) : (
          <div className="empty-source">
            <b>아직 이 장소에 연결된 문화유산 이야기가 없습니다.</b>
            <span>관광지 자료를 동기화하면 전시와 유물 이야기가 표시됩니다.</span>
          </div>
        )}
      </div>
      {!!cultureData?.exhibitions.length && (
        <>
          <div className="label">지금 볼 수 있는 전시</div>
          <div className="source-list">
            {cultureData.exhibitions.map((source) => <PublicSourceRow key={source.id} source={source} />)}
          </div>
        </>
      )}
      <div className="button-stack">
        <button className="primary" type="button" onClick={() => officialUrl && window.open(officialUrl, "_blank", "noopener,noreferrer")} disabled={!officialUrl}>
          <BookOpen aria-hidden />
          관광 정보 열기
        </button>
      </div>
    </div>
  );
}

function PublicSourceRow({ source }: { source: PublicDataSource }) {
  const readableUrl = readableSourceUrl(source);
  const content = (
    <>
      <div>
        <b>{displaySourceTitle(source)}</b>
        <span>{sourceFact(source)}</span>
        {(source.starts_at || source.ends_at) && <em>{formatPublicPeriod(source)}</em>}
      </div>
      <small>{displayProvider(source)}</small>
    </>
  );
  return readableUrl ? (
    <a className="public-source-row" href={readableUrl} target="_blank" rel="noreferrer">
      {content}
    </a>
  ) : (
    <div className="public-source-row" role="group">
      {content}
    </div>
  );
}

function PrintScreen({ destination, onBack, onShipping }: { destination: Destination; onBack: () => void; onShipping: () => void }) {
  return (
    <div className="screen-section">
      <div className="screen-heading">
        <button className="icon-text" onClick={onBack} type="button">
          <ChevronLeft aria-hidden />
          미리보기
        </button>
      </div>
      <h1 className="title-tight">제작소에 맡기기</h1>
      <p className="desc">완성한 조각을 실제 피규어로 받아볼 수 있도록 조각나라 제작 요청을 보냅니다.</p>
      <div className="chips">
        {["7cm 책상형", "키링", "자석", "단색", "컬러"].map((item, index) => (
          <button className={`chip ${index === 0 ? "active" : ""}`} key={item} type="button">
            {item}
          </button>
        ))}
      </div>
      <div className="progress-list">
        <Step done title="GLB 미리보기" text={`${destination.name} texture preview`} tag="GLB" />
        <Step done title="출력 STL" text="Blender 스케일 정규화와 받침대 생성" tag="STL" />
        <Step now title="3MF 패키지" text="컬러/재질 출력 옵션과 검사 리포트 묶음" tag="3MF" />
      </div>
      <div className="button-stack">
        <button className="primary" onClick={onShipping} type="button">
          <Send aria-hidden />
          제작 요청 보내기
        </button>
        <button className="secondary" type="button">
          <Download aria-hidden />
          파일만 내려받기
        </button>
        <button className="secondary" type="button">
          <Wallet aria-hidden />
          예상 비용 보기
        </button>
      </div>
    </div>
  );
}

function ShippingScreen({ onHome }: { onHome: () => void }) {
  return (
    <div className="screen-section">
      <h1 className="title-tight">조각이 오고 있어요</h1>
      <p className="desc">여행 후 제작된 피규어가 집으로 배송됩니다. 제작 사진도 함께 확인할 수 있어요.</p>
      <div className="progress-list">
        <Step done title="제작 요청 완료" text="조각 정보가 제작소에 도착했어요." tag="완료" />
        <Step done title="출력 준비 완료" text="제작 가능한 파일로 확인됐어요." tag="완료" />
        <Step now title="3D 프린팅 진행" text="조각나라 작업대에서 출력 중입니다." tag="진행" />
        <Step title="배송 시작" text="송장번호가 등록되면 알림을 보냅니다." tag="대기" />
      </div>
      <div className="button-stack">
        <button className="primary" type="button">
          <Truck aria-hidden />
          배송 추적하기
        </button>
        <button className="secondary" type="button">
          <ImageIcon aria-hidden />
          제작 사진 보기
        </button>
        <button className="secondary" onClick={onHome} type="button">
          <Home aria-hidden />
          조각장으로 돌아가기
        </button>
      </div>
    </div>
  );
}

function ProfileScreen({ userName, onLogin }: { userName: string; onLogin: () => void }) {
  return (
    <div className="screen-section">
      <h1 className="title-tight">내정보</h1>
      <p className="desc">{userName || "게스트"} 계정으로 둘러보는 중입니다. 제작·배송 전에는 이메일, Google, Kakao 계정 연결을 요구할 수 있습니다.</p>
      <div className="action-list">
        <ActionRow icon={<Mail />} title="이메일 로그인" text="Magic link 또는 인증코드 연결" tag="AUTH" />
        <ActionRow icon={<User />} title="Google / Kakao" text="OAuth 앱 키 발급 후 활성화" tag="OAUTH" />
        <ActionRow icon={<Truck />} title="배송지 관리" text="제작 요청 시 주소와 연락처 저장" tag="SHIP" />
      </div>
      <div className="button-stack">
        <button className="secondary" onClick={onLogin} type="button">
          <RefreshCw aria-hidden />
          로그인 화면으로
        </button>
      </div>
    </div>
  );
}

function ActionRow({ icon, title, text, tag, onClick }: { icon: React.ReactNode; title: string; text: string; tag: string; onClick?: () => void }) {
  const content = (
    <>
      <span className="row-icon">{icon}</span>
      <span>
        <strong>{title}</strong>
        <small>{text}</small>
      </span>
      <em>{tag}</em>
    </>
  );

  if (onClick) {
    return (
      <button className="action-row button-row" onClick={onClick} type="button">
        {content}
      </button>
    );
  }
  return <div className="action-row">{content}</div>;
}

function Step({ done, now, title, text, tag }: { done?: boolean; now?: boolean; title: string; text: string; tag: string }) {
  return (
    <div className={`step ${done ? "done" : ""} ${now ? "now" : ""}`}>
      <i />
      <span>
        <b>{title}</b>
        <small>{text}</small>
      </span>
      <em>{tag}</em>
    </div>
  );
}

function TabBar({ active, onNavigate }: { active: Screen; onNavigate: (screen: Screen) => void }) {
  const tabs: Array<{ id: Screen; label: string; icon: React.ReactNode }> = [
    { id: "home", label: "홈", icon: <Home /> },
    { id: "explore", label: "탐색", icon: <Search /> },
    { id: "unlock", label: "해금", icon: <MapPin /> },
    { id: "preview", label: "제작", icon: <Box /> },
    { id: "profile", label: "내정보", icon: <User /> }
  ];

  return (
    <nav className="tabbar" aria-label="주요 메뉴">
      {tabs.map((tab) => (
        <button className={`tab ${active === tab.id ? "active" : ""}`} onClick={() => onNavigate(tab.id)} type="button" key={tab.id}>
          {tab.icon}
          {tab.label}
        </button>
      ))}
    </nav>
  );
}

function GoogleLogo() {
  return (
    <svg className="google-mark" viewBox="0 0 48 48" aria-hidden="true">
      <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5Z" />
      <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65Z" />
      <path fill="#FBBC05" d="M10.53 28.59A14.48 14.48 0 0 1 9.75 24c0-1.59.28-3.14.78-4.59l-7.98-6.19A23.89 23.89 0 0 0 0 24c0 3.86.93 7.5 2.56 10.78l7.97-6.19Z" />
      <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48Z" />
    </svg>
  );
}

function openRoute(destination: Destination) {
  window.open(`https://www.openstreetmap.org/directions?to=${destination.lat}%2C${destination.lon}`, "_blank", "noopener,noreferrer");
}

function stripPartSuffix(value: string) {
  return value
    .replace(/\s+(base|prop|head|pattern|pose|ticket|scroll|jar|body|texture|tag|season)$/i, "")
    .replace(/\s+/g, " ")
    .trim();
}

function cleanPublicField(value?: string | null) {
  if (!value) return null;
  const text = value.trim().replace(/\s+/g, " ");
  if (!text) return null;
  if (/JOGAK|로컬\s*fallback|fallback|카탈로그|메타데이터|endpoint|openapi|TourAPI 연동 대상|API 승인/i.test(text)) return null;
  return text;
}

function cleanSourceSummary(value?: string | null) {
  if (!value) return null;
  let text = value.trim().replace(/\s+/g, " ");
  if (!text) return null;
  text = text.replace(
    /(.+?)의 장소성\((.+?)\)을 반영하는 JOGAK 해금 부품 메타데이터입니다\.?\s*/g,
    "$1의 $2 분위기를 담은 부품입니다. "
  );
  text = text.replace(/AI 생성 시 형태를 훼손하지 않고\s*(.+?)의 정체성을 유지합니다\.?/g, (_, name: string) => {
    const readableName = stripPartSuffix(name);
    return `${readableName}의 형태와 분위기를 살립니다.`;
  });
  text = text
    .replace(/JOGAK 해금 부품 메타데이터입니다\.?\s*/g, "")
    .replace(/AI 생성 시[^.。]+[.。]\s*/g, "")
    .replace(/생성 제약에 반영됩니다\.?/g, "")
    .replace(/\s+/g, " ")
    .trim();
  if (!text || /JOGAK|카탈로그|메타데이터|endpoint|openapi|API 승인/i.test(text)) return null;
  return text;
}

function displaySourceTitle(source: PublicDataSource) {
  return stripPartSuffix(cleanPublicField(source.title) || "문화유산 요소");
}

function displayProvider(source: PublicDataSource) {
  const provider = cleanPublicField(source.provider);
  const institution = cleanPublicField(source.institution);
  if (provider?.includes("한국관광공사")) return "한국관광공사";
  if (provider?.includes("문화체육관광부")) return "문화체육관광부";
  return provider || institution || "문화유산 자료";
}

function sourceFact(source: PublicDataSource) {
  const summary = cleanSourceSummary(source.summary);
  if (summary) return summary;
  const facts = [source.period, source.material, source.institution].map(cleanPublicField).filter(Boolean);
  return facts.length ? facts.join(" · ") : `${displaySourceTitle(source)}와 연결된 이야기입니다.`;
}

function readableSourceUrl(source: PublicDataSource) {
  const url = source.source_url?.trim();
  if (!url || !/^https?:\/\//i.test(url)) return undefined;
  const lowerUrl = url.toLowerCase();
  if (lowerUrl.includes("data.go.kr") || lowerUrl.includes("openapi") || lowerUrl.includes("/api/") || lowerUrl.includes("servicekey")) {
    return undefined;
  }
  return url;
}

function heritagePartSummary(parts: PartAsset[], destination: Destination) {
  const sourceTitles = parts
    .flatMap((part) => part.public_sources)
    .map(displaySourceTitle)
    .filter(Boolean);
  const materials = parts
    .flatMap((part) => part.public_sources)
    .map((source) => cleanPublicField(source.material))
    .filter(Boolean);
  const uniqueTitles = Array.from(new Set(sourceTitles)).slice(0, 3);
  const uniqueMaterials = Array.from(new Set(materials)).slice(0, 2);
  if (!uniqueTitles.length) return `${destination.name}의 시대와 소재 이야기를 조각에 담을 준비를 하고 있습니다.`;
  const titleText = uniqueTitles.join(", ");
  const tail = sourceTitles.length > uniqueTitles.length ? " 등이" : "이";
  const materialText = uniqueMaterials.length ? ` ${uniqueMaterials.join(", ")}의 질감도 함께 살립니다.` : "";
  return `${titleText}${tail} ${destination.name}의 분위기와 이어집니다.${materialText}`;
}

function officialDestinationUrl(destination: Destination, cultureData: DestinationCulture | null, parts: PartAsset[]) {
  const readableSource = [
    ...(cultureData?.destination_sources || []),
    ...parts.flatMap((part) => part.public_sources)
  ].map(readableSourceUrl).find(Boolean);
  if (readableSource) return readableSource;
  if (destination.name.includes("국립중앙박물관")) return "https://www.museum.go.kr/site/main/home";
  return `https://korean.visitkorea.or.kr/search/search_list.do?keyword=${encodeURIComponent(destination.name)}`;
}

function formatPublicPeriod(source: PublicDataSource) {
  const formatter = new Intl.DateTimeFormat("ko-KR", { year: "numeric", month: "short", day: "numeric" });
  const start = source.starts_at ? formatter.format(new Date(source.starts_at)) : null;
  const end = source.ends_at ? formatter.format(new Date(source.ends_at)) : null;
  if (start && end) return `${start} - ${end}`;
  return start || end || "";
}

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

const EDITOR_STAGE_WIDTH = 312;
const EDITOR_STAGE_HEIGHT = 288;

const EDITOR_SLOT_SIZES: Record<string, { width: number; height: number }> = {
  base: { width: 154, height: 72 },
  head: { width: 80, height: 80 },
  body: { width: 94, height: 94 },
  hand_prop: { width: 72, height: 72 },
  back_prop: { width: 100, height: 88 },
  pattern: { width: 72, height: 72 },
  texture: { width: 72, height: 72 },
  pose: { width: 86, height: 86 },
  tag: { width: 64, height: 64 },
  season: { width: 72, height: 72 }
};

function layerSize(slot: string) {
  return EDITOR_SLOT_SIZES[slot] || { width: 72, height: 72 };
}

function clampLayerPosition(layer: EditorLayer): EditorLayer {
  const size = layerSize(layer.slot);
  return {
    ...layer,
    x: clamp(layer.x, 0, EDITOR_STAGE_WIDTH - size.width),
    y: clamp(layer.y, 0, EDITOR_STAGE_HEIGHT - size.height)
  };
}

function defaultLayerPlacement(slot: string, index: number): Pick<EditorLayer, "x" | "y" | "z"> {
  const size = layerSize(slot);
  if (slot === "base" || slot === "pattern" || slot === "texture") {
    return { x: (EDITOR_STAGE_WIDTH - size.width) / 2, y: 198 + Math.min(index, 2) * 7, z: 1 + index };
  }
  if (slot === "head") {
    return { x: (EDITOR_STAGE_WIDTH - size.width) / 2, y: 18 + index * 3, z: 24 + index };
  }
  if (slot === "back_prop") {
    return { x: index % 2 ? 176 : 36, y: 86 + Math.floor(index / 2) * 16, z: 4 + index };
  }
  if (slot === "hand_prop" || slot === "pose" || slot === "tag") {
    return { x: index % 2 ? 196 : 42, y: 110 + Math.floor(index / 2) * 16, z: 18 + index };
  }
  if (slot === "body" || slot === "season") {
    return { x: 110 + (index % 2) * 18, y: 116 + Math.floor(index / 2) * 14, z: 14 + index };
  }
  return { x: 72 + (index % 3) * 58, y: 86 + Math.floor(index / 3) * 44, z: index + 1 };
}

function modeLabel(slot: string) {
  if (slot === "head") return "머리 착용";
  if (slot === "hand_prop" || slot === "pose" || slot === "tag") return "손/몸 연결";
  if (slot === "base" || slot === "pattern" || slot === "texture") return "원판/베이스";
  if (slot === "back_prop") return "뒤쪽 배경";
  return "자유 배치";
}

function initialUnlockedPartIds(parts: PartAsset[], email: string) {
  if (email.trim().toLowerCase() === REVIEW_UNLOCK_EMAIL) {
    return parts.map((part) => part.id);
  }
  return parts.filter((part) => part.unlocked).map((part) => part.id);
}

function buildUnlockedLayers(parts: PartAsset[], unlockedIds: string[]): EditorLayer[] {
  const unlocked = new Set(unlockedIds);
  return parts
    .filter((part) => part.image_url && (part.unlocked || unlocked.has(part.id) || unlocked.has(part.name)))
    .slice(0, 10)
    .map((part, index) => {
      const placement = defaultLayerPlacement(part.slot, index);
      return {
        id: `layer-${part.id}`,
        partAssetId: part.id,
        label: part.name,
        slot: part.slot,
        x: placement.x,
        y: placement.y,
        scale: part.slot === "base" ? 1.08 : 1,
        rotation: 0,
        z: placement.z,
        color: "#d9d3c8",
        imageUrl: part.image_url
      };
    });
}
