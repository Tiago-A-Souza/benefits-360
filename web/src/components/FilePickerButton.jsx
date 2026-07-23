import { useRef } from "react";

export default function FilePickerButton({
  accept,
  multiple = false,
  disabled = false,
  onFiles,
  children,
  className = "",
}) {
  const inputRef = useRef(null);

  function handleChange(e) {
    const files = Array.from(e.target.files || []);
    if (files.length) onFiles?.(files);
    e.target.value = "";
  }

  return (
    <>
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        multiple={multiple}
        hidden
        onChange={handleChange}
      />
      <button
        type="button"
        className={className}
        disabled={disabled}
        onClick={() => inputRef.current?.click()}
      >
        {children}
      </button>
    </>
  );
}
