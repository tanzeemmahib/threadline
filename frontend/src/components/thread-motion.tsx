import Link from "next/link";
import {
  forwardRef,
  type ButtonHTMLAttributes,
  type ComponentProps,
  type InputHTMLAttributes,
  type ReactNode,
} from "react";
import type { ThreadConnectionState, ThreadResolutionPhase } from "@/lib/thread-motion";

type ThreadArrowDirection = "forward" | "external" | "down";
type ThreadControlMotion = "signature" | "connect" | "quiet" | "none";
type ThreadControlVariant = "primary" | "secondary" | "quiet" | "danger" | "bare";

function cx(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(" ");
}

export function ThreadNode({ state = "idle", className }: { state?: "idle" | "active" | "resolved" | "interrupted"; className?: string }) {
  return <span className={cx("thread-node", `thread-node--${state}`, className)} aria-hidden="true" />;
}

export function SignalPath({ className, phase = "idle", d = "M1 5 H27" }: { className?: string; phase?: "idle" | "tracing" | "resolved" | "interrupted"; d?: string }) {
  return <path className={cx("signal-path", `signal-path--${phase}`, className)} d={d} pathLength="1" vectorEffect="non-scaling-stroke" />;
}

export function ThreadPulse({ className }: { className?: string }) {
  return <i className={cx("thread-pulse", className)} data-thread-signal aria-hidden="true" />;
}

export function ThreadArrow({ direction = "forward" }: { direction?: ThreadArrowDirection }) {
  const stem = direction === "down" ? "M12 1 V7" : direction === "external" ? "M2 8 L8 2" : "M1 5 H22";
  const head = direction === "down" ? "M9 6 L12 9 L15 6" : direction === "external" ? "M4 2 H8 V6" : "M19 2 L23 5 L19 8";
  return (
    <svg className={`thread-arrow thread-arrow--${direction}`} viewBox="0 0 24 10" aria-hidden="true">
      <path className="thread-arrow__stem" d={stem} pathLength="1" />
      <path className="thread-arrow__head" d={head} pathLength="1" />
    </svg>
  );
}

export function ThreadTrace({ className, state = "fragmented" }: { className?: string; state?: ThreadConnectionState }) {
  return (
    <svg className={cx("thread-trace", className)} data-thread-state={state} viewBox="0 0 100 12" preserveAspectRatio="none" aria-hidden="true">
      <circle className="thread-trace__node thread-trace__node--origin" cx="3" cy="6" r="1.35" vectorEffect="non-scaling-stroke" />
      <SignalPath phase={state === "interrupted" ? "interrupted" : state === "fragmented" ? "idle" : state === "connected" ? "resolved" : "tracing"} d="M4.5 6 H95.5" />
      <circle className="thread-trace__node thread-trace__node--destination" cx="97" cy="6" r="1.35" vectorEffect="non-scaling-stroke" />
      <circle className="thread-trace__signal" cx="3" cy="6" r="0.8" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

export function TraceBorder({ className }: { className?: string }) {
  return (
    <span className={cx("trace-border", className)} aria-hidden="true">
      <svg viewBox="0 0 100 40" preserveAspectRatio="none">
        <path d="M1 20 V39 H99 V20" pathLength="1" vectorEffect="non-scaling-stroke" />
      </svg>
      <ThreadNode className="trace-border__origin" />
      <ThreadNode className="trace-border__destination" />
    </span>
  );
}

function ThreadControlDecor({ motion, arrow }: { motion: ThreadControlMotion; arrow: ThreadArrowDirection | false }) {
  if (motion === "none") return arrow ? <ThreadArrow direction={arrow} /> : null;
  return (
    <>
      {motion === "signature" ? <TraceBorder /> : null}
      <span className="thread-control__connection" aria-hidden="true"><i /><b /><i /></span>
      <ThreadPulse />
      {arrow ? <ThreadArrow direction={arrow} /> : null}
    </>
  );
}

export interface ThreadButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ThreadControlVariant;
  motion?: ThreadControlMotion;
  arrow?: ThreadArrowDirection | false;
  magnetic?: boolean;
  proximity?: boolean;
}

export const ThreadButton = forwardRef<HTMLButtonElement, ThreadButtonProps>(function ThreadButton(
  {
    variant = "primary",
    motion = variant === "primary" ? "signature" : variant === "secondary" ? "connect" : "quiet",
    arrow = false,
    magnetic = false,
    proximity = false,
    className,
    children,
    type = "button",
    ...props
  },
  ref,
) {
  return (
    <button
      {...props}
      ref={ref}
      type={type}
      className={cx(`button-${variant}`, "thread-control", className)}
      data-thread-control={motion}
      data-thread-magnetic={magnetic || undefined}
      data-thread-proximity={proximity || undefined}
    >
      <span className="thread-control__content" data-thread-content>{children}</span>
      <ThreadControlDecor motion={motion} arrow={arrow} />
    </button>
  );
});

export type ThreadLinkProps = ComponentProps<typeof Link> & {
  variant?: "primary" | "secondary" | "text" | "nav" | "bare";
  motion?: ThreadControlMotion;
  arrow?: ThreadArrowDirection | false;
  bridge?: boolean;
  current?: boolean;
  magnetic?: boolean;
  proximity?: boolean;
};

export const ThreadLink = forwardRef<HTMLAnchorElement, ThreadLinkProps>(function ThreadLink(
  {
    variant = "text",
    motion = variant === "primary" ? "signature" : variant === "secondary" ? "connect" : variant === "bare" ? "none" : "quiet",
    arrow = false,
    bridge = false,
    current = false,
    magnetic = false,
    proximity = false,
    className,
    children,
    ...props
  },
  ref,
) {
  const variantClass = variant === "primary" ? "button-primary" : variant === "secondary" ? "button-secondary" : variant === "nav" ? "site-nav__link" : variant === "text" ? "text-link" : undefined;
  return (
    <Link
      {...props}
      ref={ref}
      className={cx(variantClass, "thread-control", className)}
      aria-current={current ? "page" : props["aria-current"]}
      data-thread-control={motion}
      data-thread-magnetic={magnetic || undefined}
      data-thread-proximity={proximity || undefined}
      data-threadline-route={bridge || undefined}
    >
      <span className="thread-control__content" data-thread-content>{children}</span>
      <ThreadControlDecor motion={motion} arrow={arrow} />
    </Link>
  );
});

export interface ThreadInputProps extends InputHTMLAttributes<HTMLInputElement> {
  state?: "idle" | "inspecting" | "valid" | "invalid";
  leading?: ReactNode;
  wrapperClassName?: string;
}

export const ThreadInput = forwardRef<HTMLInputElement, ThreadInputProps>(function ThreadInput(
  { state = "idle", leading, wrapperClassName, className, "aria-invalid": ariaInvalid, ...props },
  ref,
) {
  const invalid = ariaInvalid === true || ariaInvalid === "true" || state === "invalid";
  return (
    <span className={cx("thread-input", wrapperClassName)} data-thread-input-state={invalid ? "invalid" : state}>
      {leading ? <span className="thread-input__leading" aria-hidden="true">{leading}</span> : <ThreadNode className="thread-input__node" />}
      <input {...props} ref={ref} className={className} aria-invalid={invalid || undefined} />
      <TraceBorder className="thread-input__trace" />
    </span>
  );
});

export function ThreadLoader({ label = "Searching for a connection", compact = false, announce = true }: { label?: string; compact?: boolean; announce?: boolean }) {
  return (
    <span className={cx("thread-loader", compact && "thread-loader--compact")} role={announce ? "status" : undefined} aria-live={announce ? "polite" : undefined} aria-hidden={announce ? undefined : true}>
      <span className="thread-loader__geometry" aria-hidden="true">
        <i /><b /><i /><b /><i /><em />
      </span>
      {announce ? <span className="sr-only">{label}</span> : null}
    </span>
  );
}

export function ConnectionState({ state, label, announce = false, className }: { state: ThreadConnectionState; label: string; announce?: boolean; className?: string }) {
  return (
    <span className={cx("connection-state", className)} data-connection-state={state} role={announce ? "img" : undefined} aria-label={announce ? label : undefined} aria-hidden={announce ? undefined : true}>
      <ThreadTrace state={state} />
    </span>
  );
}

export function ResolutionTransition({ phase, children, className }: { phase: ThreadResolutionPhase; children: ReactNode; className?: string }) {
  return <div className={cx("resolution-transition", className)} data-resolution-phase={phase}>{children}</div>;
}
