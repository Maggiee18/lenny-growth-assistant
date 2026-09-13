import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { ArtifactViewer } from "@/components/ArtifactViewer";
import type { ArtifactOut } from "@/lib/types";

const baseArtifact: ArtifactOut = {
  id: "a1",
  session_id: "s1",
  message_id: null,
  artifact_type: "markdown",
  title: "My Essay",
  content: "# Hello\n\nSome **bold** text.",
  artifact_metadata: {},
  created_at: new Date().toISOString(),
};

describe("ArtifactViewer", () => {
  it("shows the empty state when no artifact is provided", () => {
    render(<ArtifactViewer artifact={null} onClose={vi.fn()} />);
    expect(screen.getByText(/will appear here/i)).toBeInTheDocument();
  });

  it("renders markdown content through react-markdown, not raw HTML", () => {
    render(<ArtifactViewer artifact={baseArtifact} onClose={vi.fn()} />);
    expect(screen.getByRole("heading", { name: "Hello" })).toBeInTheDocument();
    expect(screen.getByText("bold")).toBeInTheDocument();
  });

  it("never renders raw HTML tags embedded in markdown content as markup", () => {
    const withEmbeddedHtml: ArtifactOut = {
      ...baseArtifact,
      content: "# Title\n\n<img src=x onerror=alert(1)>",
    };
    render(<ArtifactViewer artifact={withEmbeddedHtml} onClose={vi.fn()} />);
    // react-markdown without rehype-raw prints the tag as literal text,
    // it must NOT create a real <img> element with an onerror handler.
    const img = screen.queryByRole("img");
    expect(img).not.toBeInTheDocument();
  });

  it("renders HTML artifacts inside an iframe with an empty sandbox attribute", () => {
    const htmlArtifact: ArtifactOut = {
      ...baseArtifact,
      artifact_type: "html",
      content: "<h1>Hi</h1>",
    };
    render(<ArtifactViewer artifact={htmlArtifact} onClose={vi.fn()} />);
    const iframe = screen.getByTitle("My Essay") as HTMLIFrameElement;
    expect(iframe).toBeInTheDocument();
    expect(iframe.getAttribute("sandbox")).toBe("");
  });

  it("toggling to source view shows the raw content as text", async () => {
    render(<ArtifactViewer artifact={baseArtifact} onClose={vi.fn()} />);
    fireEvent.click(screen.getByText("Source"));
    expect(screen.getByText(/# Hello/)).toBeInTheDocument();
  });

  it("calls onClose when the close button is clicked", () => {
    const onClose = vi.fn();
    render(<ArtifactViewer artifact={baseArtifact} onClose={onClose} />);
    fireEvent.click(screen.getByLabelText("Close artifact viewer"));
    expect(onClose).toHaveBeenCalledOnce();
  });
});
