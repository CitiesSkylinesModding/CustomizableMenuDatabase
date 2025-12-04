# How to use

1. Install pixi
    see [pixi installation guide](https://pixi.sh/latest/installation/)
2. Run command

    ```bash
    pixi run build
    ```

## Edit

Use any CSV editor to edit `ModsData.csv`, such as Excel, VS Code etc.
Preset Keywords (Built-in Styles)

### Preset `Srcs` keywords

- ALPHA
- BETA
- EXP
- RC
- BROKEN

The value is rendered using a built-in predefined style
Any custom style is ignored for this entry
Visual appearance (color, shape, emphasis) is controlled by the system

in csv, words are split by `;` (semicolon)

```text
ALPHA;BETA;EXP
```

### Style

INI style key-value pairs, separated by `;` (semicolon)

```text
KEY=VALUE;KEY=VALUE;...
```
