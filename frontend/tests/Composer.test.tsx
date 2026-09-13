import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { Composer } from "@/components/Composer";

describe("Composer", () => {
  it("calls onSend with trimmed content and clears the input on Enter", () => {
    const onSend = vi.fn();
    render(<Composer onSend={onSend} disabled={false} />);
    const textarea = screen.getByLabelText("Message");
    fireEvent.change(textarea, { target: { value: "  hello world  " } });
    fireEvent.keyDown(textarea, { key: "Enter", shiftKey: false });
    expect(onSend).toHaveBeenCalledWith("hello world");
    expect((textarea as HTMLTextAreaElement).value).toBe("");
  });

  it("does not submit on Shift+Enter (newline instead)", () => {
    const onSend = vi.fn();
    render(<Composer onSend={onSend} disabled={false} />);
    const textarea = screen.getByLabelText("Message");
    fireEvent.change(textarea, { target: { value: "line one" } });
    fireEvent.keyDown(textarea, { key: "Enter", shiftKey: true });
    expect(onSend).not.toHaveBeenCalled();
  });

  it("does not submit blank/whitespace-only content", () => {
    const onSend = vi.fn();
    render(<Composer onSend={onSend} disabled={false} />);
    const textarea = screen.getByLabelText("Message");
    fireEvent.change(textarea, { target: { value: "   " } });
    fireEvent.keyDown(textarea, { key: "Enter" });
    expect(onSend).not.toHaveBeenCalled();
  });

  it("disables the send button while disabled=true", () => {
    render(<Composer onSend={vi.fn()} disabled={true} />);
    expect(screen.getByText("Send")).toBeDisabled();
  });

  it("clicking a suggestion fills the composer", () => {
    render(<Composer onSend={vi.fn()} disabled={false} />);
    const suggestion = screen.getByText("Write a Ship 30 essay about pricing strategy");
    fireEvent.click(suggestion);
    const textarea = screen.getByLabelText("Message") as HTMLTextAreaElement;
    expect(textarea.value).toBe("Write a Ship 30 essay about pricing strategy");
  });
});
