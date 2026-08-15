"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { threadMotion } from "@/lib/thread-motion";

const CONTROL_SELECTOR = "[data-thread-control], [data-threadline-cta], .button-primary, .button-secondary, .button-quiet, .button-danger";

function findAction(target: EventTarget | null): HTMLElement | null {
  return target instanceof Element ? target.closest<HTMLElement>(CONTROL_SELECTOR) : null;
}

function isDisabled(action: HTMLElement) {
  return (action instanceof HTMLButtonElement && action.disabled) || action.getAttribute("aria-disabled") === "true";
}

export function ThreadlineInteractionLayer() {
  const router = useRouter();
  const [navigating, setNavigating] = useState(false);
  const navigationTimer = useRef<number | null>(null);

  useEffect(() => {
    let pressedAction: HTMLElement | null = null;
    let magneticAction: HTMLElement | null = null;
    let lastPointer = { x: 0, y: 0 };
    const timers = new Set<number>();
    const frames = new Set<number>();
    const reducedMotionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    const finePointerQuery = window.matchMedia("(hover: hover) and (pointer: fine)");
    const schedule = (callback: () => void, delay: number) => {
      const timer = window.setTimeout(() => {
        timers.delete(timer);
        callback();
      }, delay);
      timers.add(timer);
      return timer;
    };
    const scheduleFrame = (callback: () => void) => {
      const frame = window.requestAnimationFrame(() => {
        frames.delete(frame);
        callback();
      });
      frames.add(frame);
      return frame;
    };
    const resetMotion = (action: HTMLElement | null) => {
      if (!action) return;
      action.style.removeProperty("--thread-magnetic-x");
      action.style.removeProperty("--thread-magnetic-y");
      action.style.removeProperty("--thread-content-x");
      action.style.removeProperty("--thread-content-y");
      action.style.removeProperty("--thread-proximity");
      action.classList.remove("is-tracing");
    };
    const resetAllMotion = () => {
      magneticAction = null;
      document.querySelectorAll<HTMLElement>("[data-thread-magnetic], [data-thread-proximity]").forEach(resetMotion);
    };
    const release = (action: HTMLElement | null) => {
      if (!action) return;
      action.classList.remove("is-pressing", "is-releasing");
      scheduleFrame(() => action.isConnected && action.classList.add("is-releasing"));
      schedule(() => action.classList.remove("is-releasing"), 280);
    };
    const pulse = (action: HTMLElement) => {
      if (isDisabled(action)) return;
      action.classList.remove("is-pulsing");
      scheduleFrame(() => action.isConnected && action.classList.add("is-pulsing"));
      schedule(() => action.classList.remove("is-pulsing"), threadMotion.standard + 40);
    };
    const updatePointerMotion = () => {
      if (reducedMotionQuery.matches || !finePointerQuery.matches) {
        resetAllMotion();
        return;
      }
      if (magneticAction?.isConnected) {
        const bounds = magneticAction.getBoundingClientRect();
        const xRatio = Math.max(-1, Math.min(1, (lastPointer.x - (bounds.left + bounds.width / 2)) / (bounds.width / 2)));
        const yRatio = Math.max(-1, Math.min(1, (lastPointer.y - (bounds.top + bounds.height / 2)) / (bounds.height / 2)));
        magneticAction.style.setProperty("--thread-magnetic-x", `${(xRatio * threadMotion.magneticControl).toFixed(2)}px`);
        magneticAction.style.setProperty("--thread-magnetic-y", `${(yRatio * threadMotion.magneticControl).toFixed(2)}px`);
        magneticAction.style.setProperty("--thread-content-x", `${(xRatio * threadMotion.magneticContent).toFixed(2)}px`);
        magneticAction.style.setProperty("--thread-content-y", `${(yRatio * threadMotion.magneticContent).toFixed(2)}px`);
      }
      document.querySelectorAll<HTMLElement>("[data-thread-proximity]").forEach((action) => {
        const bounds = action.getBoundingClientRect();
        const dx = Math.max(bounds.left - lastPointer.x, 0, lastPointer.x - bounds.right);
        const dy = Math.max(bounds.top - lastPointer.y, 0, lastPointer.y - bounds.bottom);
        const distance = Math.hypot(dx, dy);
        const strength = Math.max(0, 1 - distance / threadMotion.proximityRadius);
        action.style.setProperty("--thread-proximity", strength.toFixed(3));
      });
    };
    let pointerFrame: number | null = null;
    const handlePointerMove = (event: PointerEvent) => {
      if (reducedMotionQuery.matches || !finePointerQuery.matches) return;
      lastPointer = { x: event.clientX, y: event.clientY };
      if (pointerFrame !== null) return;
      pointerFrame = window.requestAnimationFrame(() => {
        pointerFrame = null;
        updatePointerMotion();
      });
    };
    const handlePointerOver = (event: PointerEvent) => {
      const action = findAction(event.target);
      if (!action || isDisabled(action) || (event.relatedTarget instanceof Node && action.contains(event.relatedTarget))) return;
      action.classList.add("is-tracing");
      if (action.hasAttribute("data-thread-magnetic") && !reducedMotionQuery.matches && finePointerQuery.matches) magneticAction = action;
    };
    const handlePointerOut = (event: PointerEvent) => {
      const action = findAction(event.target);
      if (!action || (event.relatedTarget instanceof Node && action.contains(event.relatedTarget))) return;
      action.classList.remove("is-tracing");
      if (magneticAction === action) magneticAction = null;
      resetMotion(action);
    };
    const handlePointerDown = (event: PointerEvent) => {
      if (event.button !== 0) return;
      const action = findAction(event.target);
      if (!action || isDisabled(action)) return;
      if (pressedAction && pressedAction !== action) release(pressedAction);
      pressedAction = action;
      action.classList.remove("is-releasing");
      action.classList.add("is-pressing");
    };
    const handlePointerUp = (event: PointerEvent) => {
      const releasedOver = findAction(event.target);
      const action = pressedAction ?? releasedOver;
      if (action && (!pressedAction || releasedOver === pressedAction)) pulse(action);
      release(action);
      pressedAction = null;
    };
    const handlePointerCancel = () => {
      release(pressedAction);
      pressedAction = null;
      resetMotion(magneticAction);
      magneticAction = null;
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.repeat || (event.key !== "Enter" && event.key !== " ")) return;
      const action = findAction(event.target);
      if (!action || isDisabled(action) || (event.key === " " && action instanceof HTMLAnchorElement)) return;
      pressedAction = action;
      action.classList.remove("is-releasing");
      action.classList.add("is-pressing");
    };
    const handleKeyUp = (event: KeyboardEvent) => {
      if (event.key !== "Enter" && event.key !== " ") return;
      release(pressedAction ?? findAction(event.target));
      pressedAction = null;
    };
    const handleRouteClick = (event: MouseEvent) => {
      const action = findAction(event.target);
      if (!action || !action.hasAttribute("data-threadline-route")) return;
      if (!(action instanceof HTMLAnchorElement) || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || action.target === "_blank" || action.hasAttribute("download")) return;
      const destination = new URL(action.href, window.location.href);
      if (destination.origin !== window.location.origin) return;
      event.preventDefault();
      event.stopPropagation();
      if (navigationTimer.current !== null) return;
      if (event.detail === 0) pulse(action);
      const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      setNavigating(!reducedMotion);
      navigationTimer.current = window.setTimeout(() => {
        navigationTimer.current = null;
        if (action.hasAttribute("data-threadline-reload")) window.location.assign(destination.href);
        else {
          router.push(`${destination.pathname}${destination.search}${destination.hash}`);
          schedule(() => setNavigating(false), threadMotion.standard);
        }
      }, reducedMotion ? 0 : 320);
    };
    const handleControlClick = (event: MouseEvent) => {
      const action = findAction(event.target);
      if (!action || isDisabled(action)) return;
      if (event.detail === 0 && !action.hasAttribute("data-threadline-route")) pulse(action);
      handleRouteClick(event);
    };

    document.addEventListener("pointerover", handlePointerOver, true);
    document.addEventListener("pointerout", handlePointerOut, true);
    document.addEventListener("pointermove", handlePointerMove, true);
    document.addEventListener("pointerdown", handlePointerDown, true);
    document.addEventListener("pointerup", handlePointerUp, true);
    document.addEventListener("pointercancel", handlePointerCancel, true);
    window.addEventListener("blur", handlePointerCancel);
    document.addEventListener("keydown", handleKeyDown, true);
    document.addEventListener("keyup", handleKeyUp, true);
    document.addEventListener("click", handleControlClick, true);
    reducedMotionQuery.addEventListener("change", resetAllMotion);
    finePointerQuery.addEventListener("change", resetAllMotion);
    return () => {
      document.removeEventListener("pointerover", handlePointerOver, true);
      document.removeEventListener("pointerout", handlePointerOut, true);
      document.removeEventListener("pointermove", handlePointerMove, true);
      document.removeEventListener("pointerdown", handlePointerDown, true);
      document.removeEventListener("pointerup", handlePointerUp, true);
      document.removeEventListener("pointercancel", handlePointerCancel, true);
      window.removeEventListener("blur", handlePointerCancel);
      document.removeEventListener("keydown", handleKeyDown, true);
      document.removeEventListener("keyup", handleKeyUp, true);
      document.removeEventListener("click", handleControlClick, true);
      reducedMotionQuery.removeEventListener("change", resetAllMotion);
      finePointerQuery.removeEventListener("change", resetAllMotion);
      timers.forEach((timer) => window.clearTimeout(timer));
      frames.forEach((frame) => window.cancelAnimationFrame(frame));
      if (pointerFrame !== null) window.cancelAnimationFrame(pointerFrame);
      if (navigationTimer.current !== null) window.clearTimeout(navigationTimer.current);
      resetAllMotion();
    };
  }, [router]);

  return (
    <div className={`threadline-route-transition ${navigating ? "is-active" : ""}`} aria-hidden="true">
      <i /><span /><i />
    </div>
  );
}
