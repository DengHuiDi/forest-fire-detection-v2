"use client";

import React, { useState, useRef, useCallback, useEffect } from "react";
import YunnanMap from "@/components/YunnanMap";

interface AiSummary {
  severity: "low" | "medium" | "high" | "critical";
  title: string;
  description: string;
  recommendations: string[];
  llmUsed: boolean;
  fallbackReason?: string | null;
  latencyMs?: number | null;
}

interface AlertEntry {
  id: number;
  time: string;
  message: string;
  isFire: boolean;
  aiSummary?: AiSummary;
  loadingAi?: boolean;
}

interface Detection {
  class: string;
  confidence: number;
  bbox?: number[];
}

const initialAlerts: AlertEntry[] = [
  {
    id: Date.now() - 900000,
    time: "09:41",
    message: "巡检正常 — 北区林带传感器在线",
    isFire: false,
  },
  {
    id: Date.now() - 1800000,
    time: "09:29",
    message: "巡检正常 — 西区热成像无异常",
    isFire: false,
  },
  {
    id: Date.now() - 3600000,
    time: "09:00",
    message: "系统自检完成 — 模型负载 23%",
    isFire: false,
  },
];

let alertIdCounter = 100;

function formatTime(): string {
  const now = new Date();
  const h = String(now.getHours()).padStart(2, "0");
  const m = String(now.getMinutes()).padStart(2, "0");
  return `${h}:${m}`;
}

const SEVERITY_META: Record<
  AiSummary["severity"],
  { label: string; classes: string; icon: string }
> = {
  low: {
    label: "低风险",
    classes: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
    icon: "○",
  },
  medium: {
    label: "中等",
    classes: "bg-amber-500/15 text-amber-300 border-amber-500/30",
    icon: "◐",
  },
  high: {
    label: "高风险",
    classes: "bg-orange-500/15 text-orange-300 border-orange-500/30",
    icon: "◕",
  },
  critical: {
    label: "紧急",
    classes: "bg-error/20 text-error border-error/50",
    icon: "●",
  },
};

export default function Home() {
  const [globalHasFire, setGlobalHasFire] = useState(false);
  const [alerts, setAlerts] = useState<AlertEntry[]>(initialAlerts);
  const [currentImage, setCurrentImage] = useState<string | null>(null);
  const [isDetecting, setIsDetecting] = useState(false);
  const [llmAvailable, setLlmAvailable] = useState(false);
  const [stats, setStats] = useState({
    fireCount: 0,
    smokeCount: 0,
    totalScanned: 127,
    onlineSensors: 48,
  });
  const fileInputRef = useRef<HTMLInputElement>(null);

  // 启动时查询 LLM 状态
  useEffect(() => {
    fetch("/api/alert/status")
      .then((r) => r.json())
      .then((d) => setLlmAvailable(!!d.enabled))
      .catch(() => setLlmAvailable(false));
  }, []);

  const fetchAiSummary = useCallback(
    async (alertId: number, detections: Detection[], imageBase64?: string) => {
      try {
        const res = await fetch("/api/alert/describe", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            detections: detections.map((d) => ({
              class_name: d.class,
              confidence: d.confidence,
              bbox: d.bbox,
            })),
            image_type: "drone",
            location_hint: "云南 — 监控区域",
            weather_hint: "气象数据接入中",
            image_base64: imageBase64,
          }),
        });

        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        if (data.status !== "success") throw new Error("describe failed");

        setAlerts((prev) =>
          prev.map((a) =>
            a.id === alertId
              ? {
                  ...a,
                  loadingAi: false,
                  aiSummary: {
                    severity: data.severity,
                    title: data.title,
                    description: data.description,
                    recommendations: data.recommendations,
                    llmUsed: data.llm_used,
                    fallbackReason: data.fallback_reason,
                    latencyMs: data.latency_ms,
                  },
                }
              : a
          )
        );
      } catch (e) {
        setAlerts((prev) =>
          prev.map((a) =>
            a.id === alertId
              ? {
                  ...a,
                  loadingAi: false,
                  aiSummary: {
                    severity: "low",
                    title: "AI 文案生成失败",
                    description: "无法连接告警分析服务,已使用规则兜底",
                    recommendations: ["检查后端服务状态"],
                    llmUsed: false,
                    fallbackReason: "frontend_fetch_error",
                  },
                }
              : a
          )
        );
      }
    },
    []
  );

  const handleDetect = useCallback(
    async (file: File) => {
      setIsDetecting(true);
      setCurrentImage(URL.createObjectURL(file));

      try {
        const formData = new FormData();
        formData.append("file", file);

        const res = await fetch("http://127.0.0.1:8000/api/detect", {
          method: "POST",
          body: formData,
        });

        if (!res.ok) throw new Error(`HTTP ${res.status}`);

        const data = await res.json();

        let imageBase64: string | undefined;
        if (data.image_base64) {
          setCurrentImage(`data:image/jpeg;base64,${data.image_base64}`);
          imageBase64 = data.image_base64;
        }

        setGlobalHasFire(data.has_fire ?? false);

        const timestamp = formatTime();
        const detections: Detection[] = data.detections ?? [];
        const hasDetections = detections.length > 0;
        const newAlertId = ++alertIdCounter;

        if (hasDetections) {
          const top = detections.reduce((best: Detection, d: Detection) =>
            d.confidence > best.confidence ? d : best
          );
          const label =
            data.has_fire
              ? `火情告警 — ${top.class} ${(top.confidence * 100).toFixed(0)}%`
              : `检测到目标 — ${top.class} ${(top.confidence * 100).toFixed(0)}%`;

          setAlerts((prev) => [
            {
              id: newAlertId,
              time: timestamp,
              message: label,
              isFire: data.has_fire,
              loadingAi: data.has_fire,
            },
            ...prev,
          ]);

          // 仅在有火情时调用 LLM (省 token)
          if (data.has_fire) {
            setStats((s) => ({ ...s, fireCount: s.fireCount + 1 }));
            fetchAiSummary(newAlertId, detections, imageBase64);
          } else {
            setStats((s) => ({ ...s, smokeCount: s.smokeCount + 1 }));
          }
        } else {
          setAlerts((prev) => [
            {
              id: newAlertId,
              time: timestamp,
              message: "巡检正常 — 未发现异常目标",
              isFire: false,
            },
            ...prev,
          ]);
        }

        setStats((s) => ({ ...s, totalScanned: s.totalScanned + 1 }));
      } catch {
        const timestamp = formatTime();
        setAlerts((prev) => [
          {
            id: ++alertIdCounter,
            time: timestamp,
            message: "系统异常 — 后端服务连接失败",
            isFire: false,
          },
          ...prev,
        ]);
      } finally {
        setIsDetecting(false);
      }
    },
    [fetchAiSummary]
  );

  const handleFileChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) handleDetect(file);
      if (fileInputRef.current) fileInputRef.current.value = "";
    },
    [handleDetect]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      const file = e.dataTransfer.files[0];
      if (file && file.type.startsWith("image/")) handleDetect(file);
    },
    [handleDetect]
  );

  const handleUploadClick = () => fileInputRef.current?.click();

  return (
    <div className="flex h-full min-h-0">
      {/* Sidebar */}
      <aside className="flex w-52 flex-shrink-0 flex-col border-r border-white/10 bg-surface-container-low">
        <div className="flex flex-col gap-1 border-b border-white/10 px-4 py-5">
          <span className="text-xs font-bold tracking-widest text-outline uppercase">
            System
          </span>
          <span className="text-sm font-bold tracking-widest text-primary">
            VIGILANT-OS
          </span>
          <span className="text-xs font-bold tracking-widest text-on-surface-variant">
            V2.5 · LLM
          </span>
        </div>

        <nav className="flex-1 overflow-y-auto px-2 py-4">
          {[
            { label: "实时监控", active: true, fire: globalHasFire },
            { label: "历史数据", active: false, fire: false },
            { label: "设备管理", active: false, fire: false },
            { label: "系统设置", active: false, fire: false },
          ].map((item) => (
            <button
              key={item.label}
              className={`mb-1 flex w-full items-center gap-2 rounded px-3 py-2 text-sm transition-colors ${
                item.active
                  ? item.fire
                    ? "bg-error/20 text-error border border-error/40"
                    : "bg-primary/10 text-primary border border-primary/30"
                  : "text-on-surface-variant hover:bg-white/5 hover:text-on-surface"
              }`}
            >
              {item.active && (
                <span
                  className={`h-1.5 w-1.5 rounded-full ${
                    item.fire ? "bg-error alarm-led" : "bg-primary"
                  }`}
                />
              )}
              {!item.active && <span className="h-1.5 w-1.5" />}
              {item.label}
            </button>
          ))}
        </nav>

        <div className="border-t border-white/10 px-4 py-4">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-xs text-on-surface-variant uppercase tracking-widest">
              LLM 告警
            </span>
            <span
              className={`font-mono text-xs ${
                llmAvailable ? "text-emerald-400" : "text-on-surface-variant/60"
              }`}
            >
              {llmAvailable ? "● 在线" : "○ 离线"}
            </span>
          </div>
          <div className="mb-3 h-1 overflow-hidden rounded-full bg-white/10">
            <div
              className={`h-full rounded-full transition-all ${
                llmAvailable ? "bg-emerald-400" : "bg-white/20"
              }`}
              style={{ width: llmAvailable ? "100%" : "30%" }}
            />
          </div>
          <div className="mb-1 flex items-center justify-between">
            <span className="text-xs text-on-surface-variant uppercase tracking-widest">
              传感器在线
            </span>
            <span className="font-mono text-xs text-primary">
              {stats.onlineSensors}
            </span>
          </div>
          <div className="h-1 overflow-hidden rounded-full bg-white/10">
            <div
              className="h-full rounded-full bg-primary transition-all"
              style={{ width: `${(stats.onlineSensors / 50) * 100}%` }}
            />
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex flex-1 flex-col overflow-hidden">
        {/* Top bar */}
        <header className="flex h-12 flex-shrink-0 items-center justify-between border-b border-white/10 bg-surface-container-low px-6">
          <div className="flex items-center gap-3">
            <span className="relative flex h-2.5 w-2.5">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary opacity-50" />
              <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-primary" />
            </span>
            <span className="font-mono text-xs tracking-widest text-on-surface-variant uppercase">
              Live Feed — Monitoring Active · LLM-Enhanced
            </span>
          </div>
          <span className="font-mono text-xs tracking-widest text-on-surface-variant">
            {new Date().toLocaleDateString("zh-CN", {
              year: "numeric",
              month: "2-digit",
              day: "2-digit",
            })}{" "}
            {formatTime()}
          </span>
        </header>

        {/* 3-column grid */}
        <div className="flex flex-1 gap-4 overflow-hidden p-4">
          {/* Left column — Fire stats */}
          <div className="flex w-52 flex-shrink-0 flex-col gap-4 overflow-y-auto">
            <div className="glass-panel px-4 py-3">
              <p className="mb-1 text-xs font-bold uppercase tracking-widest text-on-surface-variant">
                火情事件
              </p>
              <p className="font-mono text-3xl font-bold text-error">
                {stats.fireCount}
              </p>
            </div>
            <div className="glass-panel px-4 py-3">
              <p className="mb-1 text-xs font-bold uppercase tracking-widest text-on-surface-variant">
                烟雾检测
              </p>
              <p className="font-mono text-3xl font-bold text-tertiary">
                {stats.smokeCount}
              </p>
            </div>
            <div className="glass-panel px-4 py-3">
              <p className="mb-1 text-xs font-bold uppercase tracking-widest text-on-surface-variant">
                累计扫描
              </p>
              <p className="font-mono text-3xl font-bold text-primary">
                {stats.totalScanned}
              </p>
            </div>

            <div className="glass-panel mt-auto px-4 py-3">
              <p className="mb-2 text-xs font-bold uppercase tracking-widest text-on-surface-variant">
                状态
              </p>
              <div className="flex items-center gap-2">
                <span
                  className={`h-2 w-2 rounded-full ${
                    globalHasFire ? "bg-error alarm-led" : "bg-emerald-400"
                  }`}
                />
                <span
                  className={`text-sm font-medium ${
                    globalHasFire ? "text-error" : "text-emerald-400"
                  }`}
                >
                  {globalHasFire ? "火灾告警" : "系统正常"}
                </span>
              </div>
            </div>
          </div>

          {/* Middle column — Map */}
          <div className="flex flex-1 flex-col gap-4 overflow-hidden">
            <div className="glass-panel flex flex-1 flex-col overflow-hidden border border-primary/20">
              <div className="flex items-center justify-between border-b border-white/10 px-4 py-2">
                <span className="text-xs font-bold uppercase tracking-widest text-primary">
                  区域监控 — 卫星地图
                </span>
                <span className="font-mono text-xs text-on-surface-variant">
                  2D · 实时
                </span>
              </div>
              <div className="flex flex-1 items-center justify-center">
                <YunnanMap globalHasFire={globalHasFire} />
              </div>
            </div>
          </div>

          {/* Right column — Alerts + Detection workstation */}
          <div className="flex w-96 flex-shrink-0 flex-col gap-4 overflow-hidden">
            {/* Alert log */}
            <div
              className={`glass-panel flex flex-col overflow-hidden ${
                globalHasFire ? "fire-alert-panel" : ""
              }`}
            >
              <div className="flex items-center justify-between border-b border-white/10 px-4 py-2">
                <span
                  className={`text-xs font-bold uppercase tracking-widest ${
                    globalHasFire ? "text-error" : "text-error/70"
                  }`}
                >
                  实时告警动态 · AI 增强
                </span>
                {globalHasFire && (
                  <span className="h-2 w-2 rounded-full bg-error alarm-led" />
                )}
              </div>
              <div className="flex-1 overflow-y-auto">
                {alerts.map((alert) => {
                  const sev = alert.aiSummary
                    ? SEVERITY_META[alert.aiSummary.severity]
                    : null;
                  return (
                    <div
                      key={alert.id}
                      className={`flex flex-col gap-2 border-b border-white/5 px-4 py-2.5 ${
                        alert.isFire
                          ? "bg-error-container"
                          : "hover:bg-white/5"
                      }`}
                    >
                      <div className="flex items-start gap-2">
                        <div className="mt-0.5 flex-shrink-0">
                          <span
                            className={`inline-block h-1.5 w-1.5 rounded-full ${
                              alert.isFire
                                ? "bg-error alarm-led"
                                : "bg-emerald-400"
                            }`}
                          />
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="flex items-baseline justify-between gap-2">
                            <span
                              className={`font-mono text-xs ${
                                alert.isFire
                                  ? "text-on-error-container"
                                  : "text-on-surface-variant"
                              }`}
                            >
                              {alert.time}
                            </span>
                            {sev && !alert.loadingAi && (
                              <span
                                className={`rounded border px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-widest ${sev.classes}`}
                                title={
                                  alert.aiSummary?.llmUsed
                                    ? "DeepSeek-VL 生成"
                                    : "规则兜底"
                                }
                              >
                                {sev.icon} {sev.label}
                              </span>
                            )}
                          </div>
                          <p
                            className={`mt-0.5 truncate text-xs leading-snug ${
                              alert.isFire
                                ? "font-semibold text-on-error-container"
                                : "text-on-surface/80"
                            }`}
                          >
                            {alert.message}
                          </p>
                        </div>
                      </div>

                      {/* AI 摘要区 */}
                      {alert.isFire && (
                        <div className="ml-4 rounded border border-primary/20 bg-surface-container-lowest/60 p-2.5">
                          {alert.loadingAi && (
                            <div className="flex items-center gap-2 text-[11px] text-on-surface-variant/70">
                              <span className="relative flex h-1.5 w-1.5">
                                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary opacity-60" />
                                <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-primary" />
                              </span>
                              <span className="font-mono uppercase tracking-widest">
                                AI 正在分析图像...
                              </span>
                            </div>
                          )}
                          {alert.aiSummary && (
                            <div className="space-y-1.5 text-[11px] leading-relaxed">
                              <p className="font-semibold text-primary">
                                {alert.aiSummary.title}
                              </p>
                              <p className="text-on-surface/80">
                                {alert.aiSummary.description}
                              </p>
                              {alert.aiSummary.recommendations.length > 0 && (
                                <ul className="space-y-0.5 pl-3 text-on-surface/70">
                                  {alert.aiSummary.recommendations.map(
                                    (rec, i) => (
                                      <li
                                        key={i}
                                        className="list-decimal marker:text-primary/60"
                                      >
                                        {rec}
                                      </li>
                                    )
                                  )}
                                </ul>
                              )}
                              <div className="flex items-center justify-between border-t border-white/5 pt-1.5 font-mono text-[10px] text-on-surface-variant/50">
                                <span>
                                  {alert.aiSummary.llmUsed
                                    ? "● DeepSeek-VL"
                                    : "○ 规则兜底"}
                                </span>
                                {alert.aiSummary.latencyMs != null && (
                                  <span>{alert.aiSummary.latencyMs}ms</span>
                                )}
                              </div>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Detection workstation */}
            <div
              className={`glass-panel flex flex-1 flex-col overflow-hidden ${
                globalHasFire
                  ? "border-error/60 fire-alert-panel"
                  : "border-primary/30"
              }`}
            >
              <div className="flex items-center justify-between border-b border-white/10 px-4 py-2">
                <span
                  className={`text-xs font-bold uppercase tracking-widest ${
                    globalHasFire ? "text-error" : "text-primary"
                  }`}
                >
                  图像智能检测
                </span>
                {isDetecting && (
                  <span className="flex items-center gap-1.5">
                    <span className="relative flex h-2 w-2">
                      <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary opacity-50" />
                      <span className="relative inline-flex h-2 w-2 rounded-full bg-primary" />
                    </span>
                    <span className="font-mono text-xs text-primary uppercase tracking-widest">
                      检测中
                    </span>
                  </span>
                )}
              </div>

              <div className="flex flex-1 flex-col gap-3 overflow-y-auto p-3">
                {/* Image area */}
                <div
                  onClick={handleUploadClick}
                  onDrop={handleDrop}
                  onDragOver={(e) => e.preventDefault()}
                  className={`relative flex aspect-video cursor-pointer items-center justify-center overflow-hidden rounded-md border-2 border-dashed transition-colors ${
                    globalHasFire
                      ? "border-error/50 hover:border-error bg-error/5"
                      : "border-primary/30 hover:border-primary/60 bg-primary/5"
                  }`}
                >
                  {currentImage ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={currentImage}
                      alt="Detection result"
                      className="h-full w-full object-contain"
                    />
                  ) : (
                    <div className="text-center">
                      <svg
                        className={`mx-auto mb-2 ${
                          globalHasFire
                            ? "text-error/40"
                            : "text-primary/40"
                        }`}
                        width="32"
                        height="32"
                        fill="none"
                        viewBox="0 0 24 24"
                      >
                        <path
                          stroke="currentColor"
                          strokeWidth="1.5"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          d="m2.25 15.75 5.159-5.159a2.25 2.25 0 0 1 3.182 0l5.159 5.159m-1.5-1.5 1.409-1.409a2.25 2.25 0 0 1 3.182 0l2.909 2.909m-18 3.75h16.5a1.5 1.5 0 0 0 1.5-1.5V6a1.5 1.5 0 0 0-1.5-1.5H3.75A1.5 1.5 0 0 0 2.25 6v12a1.5 1.5 0 0 0 1.5 1.5Zm10.5-11.25h.008v.008h-.008V8.25Zm.375 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Z"
                        />
                      </svg>
                      <p className="text-xs text-on-surface-variant/60">
                        点击上传 / 拖拽图片
                      </p>
                    </div>
                  )}
                </div>

                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  onChange={handleFileChange}
                  className="hidden"
                />

                {/* Upload button */}
                <button
                  onClick={handleUploadClick}
                  disabled={isDetecting}
                  className={`w-full rounded py-2 text-xs font-bold uppercase tracking-widest transition-all ${
                    isDetecting
                      ? "cursor-not-allowed bg-white/5 text-on-surface-variant/40"
                      : globalHasFire
                      ? "bg-error/20 text-error border border-error/40 hover:bg-error/30"
                      : "bg-primary/10 text-primary border border-primary/30 hover:bg-primary/20"
                  }`}
                >
                  {isDetecting ? "正在分析..." : "选择图片进行检测"}
                </button>

                {/* Result hint */}
                {!currentImage && (
                  <p className="text-center text-xs text-on-surface-variant/40">
                    支持 jpg / png，模型自动标注火情与烟雾
                  </p>
                )}
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
