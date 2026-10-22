// htm bound to React.createElement: JSX-like tagged templates with no compile step.
import React from "react";
import htm from "htm";

export const html = htm.bind(React.createElement);
export { React };
