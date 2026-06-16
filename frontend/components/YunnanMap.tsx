"use client";

import React, { useEffect, useRef, useCallback } from "react";
import * as echarts from "echarts";

interface YunnanMapProps {
  globalHasFire: boolean;
}

const MONITOR_POINTS = [
  {
    name: "昆明监控中心",
    coord: [102.83, 24.88],
    description: "呈贡区监控网 — 核心节点",
  },
  {
    name: "大理林区",
    coord: [100.22, 25.58],
    description: "洱源林场 — 北部防线",
  },
  {
    name: "楚雄林带",
    coord: [101.52, 25.05],
    description: "紫溪山保护区 — 中部巡检",
  },
  {
    name: "玉溪林区",
    coord: [102.55, 24.35],
    description: "新平林场 — 南部哨点",
  },
];

const DANGER_POINT_NAME = "昆明监控中心";

export default function YunnanMap({ globalHasFire }: YunnanMapProps) {
  const chartRef = useRef<echarts.ECharts | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const geoRegisteredRef = useRef<boolean>(false);

  const buildOption = useCallback(
    (geoJson: object | null) => {
      if (!geoJson) return {};

      if (!geoRegisteredRef.current) {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        echarts.registerMap("yunnan", geoJson as any);
        geoRegisteredRef.current = true;
      }

      const effectColor = globalHasFire ? "#ffb4ab" : "#4cd7f6";
      const normalColor = "#4cd7f6";

      return {
        backgroundColor: "transparent",
        geo: {
          map: "yunnan",
          roam: false,
          zoom: 1.1,
          center: [101.5, 25.0],
          silent: true,
          itemStyle: {
            areaColor: "#171d1e",
            borderColor: "#4cd7f6",
            borderWidth: 0.8,
            shadowBlur: 6,
            shadowColor: "rgba(76, 215, 246, 0.3)",
          },
          emphasis: {
            itemStyle: {
              areaColor: "#252b2d",
              borderColor: "#4cd7f6",
              borderWidth: 1.2,
            },
          },
        },
        series: [
          {
            type: "map",
            map: "yunnan",
            roam: false,
            zoom: 1.1,
            center: [101.5, 25.0],
            silent: true,
            itemStyle: {
              areaColor: "#171d1e",
              borderColor: "#4cd7f6",
              borderWidth: 0.8,
              shadowBlur: 6,
              shadowColor: "rgba(76, 215, 246, 0.3)",
            },
            emphasis: {
              itemStyle: {
                areaColor: "#252b2d",
                borderColor: "#4cd7f6",
                borderWidth: 1.2,
              },
              label: { show: false },
            },
            select: { disabled: true },
          },
          {
            type: "effectScatter",
            coordinateSystem: "geo",
            data: MONITOR_POINTS.map((pt) => {
              const isDanger = globalHasFire && pt.name === DANGER_POINT_NAME;
              return {
                name: pt.name,
                value: [...pt.coord, 1],
                label: {
                  show: isDanger,
                  formatter: () => "{danger|高危火情警报}",
                  rich: {
                    danger: {
                      color: "#ffb4ab",
                      fontSize: 11,
                      fontWeight: "bold",
                      padding: [4, 8],
                      backgroundColor: "rgba(255,180,171,0.15)",
                      borderColor: "#ffb4ab",
                      borderWidth: 1,
                      borderRadius: 3,
                    },
                  },
                  position: "right",
                  distance: 12,
                },
                itemStyle: {
                  color: isDanger ? "#ffb4ab" : normalColor,
                  shadowBlur: isDanger ? 25 : 10,
                  shadowColor: isDanger
                    ? "rgba(255, 180, 171, 0.9)"
                    : "rgba(76, 215, 246, 0.5)",
                },
              };
            }),
            symbolSize: 8,
            showEffectOn: "render",
            rippleEffect: {
              brushType: "stroke",
              scale: globalHasFire ? 4.5 : 3,
              period: globalHasFire ? 1.2 : 4,
              color: effectColor,
            },
            zlevel: 3,
          },
        ],
        tooltip: {
          trigger: "item",
          backgroundColor: "rgba(23, 29, 30, 0.92)",
          borderColor: "#4cd7f6",
          borderWidth: 1,
          padding: [8, 12],
          textStyle: {
            color: "#dee3e6",
            fontSize: 12,
          },
          formatter: (params: { name?: string }) => {
            const pt = MONITOR_POINTS.find((p) => p.name === params.name);
            if (!pt) return "";
            const isDanger =
              globalHasFire && pt.name === DANGER_POINT_NAME;
            const status = isDanger
              ? '<span style="color:#ffb4ab;font-weight:bold;">危险</span>'
              : '<span style="color:#4cd7f6;">正常</span>';
            return `<div style="line-height:1.6;">
              <div style="font-weight:bold;margin-bottom:4px;">${pt.name}</div>
              <div style="font-size:11px;color:#bcc9cd;">${pt.description}</div>
              <div style="margin-top:4px;font-size:11px;">状态: ${status}</div>
            </div>`;
          },
        },
      };
    },
    [globalHasFire]
  );

  useEffect(() => {
    if (!containerRef.current) return;

    if (!chartRef.current) {
      chartRef.current = echarts.init(containerRef.current, null, {
        renderer: "canvas",
      });
    }

    const chart = chartRef.current;

    const loadMap = async () => {
      try {
        const resp = await fetch(
          "https://geo.datav.aliyun.com/areas_v3/bound/530000_full.json"
        );
        const geoJson = await resp.json();
        const option = buildOption(geoJson);
        chart.setOption(option, true);
      } catch (err) {
        console.error("[YunnanMap] Failed to load GeoJSON:", err);
      }
    };

    loadMap();

    const resizeObserver = new ResizeObserver(() => chart.resize());
    resizeObserver.observe(containerRef.current);

    return () => {
      resizeObserver.disconnect();
      chart.dispose();
      chartRef.current = null;
      geoRegisteredRef.current = false;
    };
  }, [buildOption]);

  useEffect(() => {
    if (!chartRef.current) return;
    if (!geoRegisteredRef.current) return;

    const loadMap = async () => {
      try {
        const resp = await fetch(
          "https://geo.datav.aliyun.com/areas_v3/bound/530000_full.json"
        );
        const geoJson = await resp.json();
        const option = buildOption(geoJson);
        chartRef.current?.setOption(option, true);
      } catch {
        // already registered, skip
      }
    };

    loadMap();
  }, [globalHasFire, buildOption]);

  return (
    <div
      ref={containerRef}
      style={{ width: "100%", height: "100%", backgroundColor: "transparent" }}
    />
  );
}
