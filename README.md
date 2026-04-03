# Amazon Review Workbook Skill

这是一个可移植的 Amazon 评论抓取与表格交付 skill。

它可以完成这些事情：

- 通过已登录的 Chrome 会话抓取 Amazon 商品评论
- 导出固定 14 列的事实工作簿
- 可选接入 DeepLX 自动补全 `评论中文版`
- 生成轻量标注输入，交给模型补全语义字段
- 将模型标注结果合并回完整工作簿
- 在追加抓取前先做覆盖率检查
- 根据历史跑数自动调优关键词词表

## 仓库结构

- `README.md`：仓库使用说明
- `SKILL.md`：给 agent 环境使用的 skill 说明
- `references/`：配置、输出契约、标注规则
- `scripts/`：核心 CLI 和处理脚本
- `agents/openai.yaml`：默认 agent prompt 元数据
- `tests/`：轻量回归测试

## 环境要求

- Python 3.11 及以上
- 一个已经登录 Amazon 的 Chrome，会话开启远程调试端口 `9222`
- 需要的 Python 包：

```bash
pip install pandas openpyxl requests websocket-client
```

- 如果想先自动翻译，再做语义标注，可选配置 DeepLX

## 配置方法

### 1. 启动带远程调试的 Chrome

Windows：

```powershell
"$env:ProgramFiles\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="$env:LOCALAPPDATA\Google\Chrome\User Data"
```

启动后确认这个 Chrome 会话里已经登录了 Amazon。

### 2. 可选配置 DeepLX

把 `.env.example` 复制为本地 `.env`，或者直接设置环境变量：

```env
DEEPLX_API_URL=https://your-deeplx-host/translate
DEEPLX_API_KEY=your-optional-key
```

## 快速开始

### 健康检查

```bash
python scripts/amazon_review_workbook.py doctor --url "<amazon-url>"
```

`doctor` 现在不只看 9222 端口是否打开，还会校验它是不是一个真正的 DevTools JSON 端点，避免“端口在监听但不是 CDP”这种假阳性。

### 抓取事实工作簿

```bash
python scripts/amazon_review_workbook.py intake --url "<amazon-url>" --output-dir "./amazon-review-output"
```

### 先跑一个 5 分钟探测版

```bash
python scripts/amazon_review_workbook.py intake --url "<amazon-url>" --output-dir "./amazon-review-output" --time-budget-minutes 5
```

### 在继续追加抓取前先看覆盖率

```bash
python scripts/amazon_review_workbook.py coverage-check --url "<amazon-url>" --db-path "./amazon-review-output/amazon_review_cache.sqlite3"
```

### 可选：先补 `评论中文版`

```bash
python scripts/amazon_review_workbook.py translate --input-json "./amazon-review-output/amazon_<asin>_review_rows_factual.json" --output-dir "./amazon-review-output"
```

### 生成标注输入

```bash
python scripts/amazon_review_workbook.py taxonomy-bootstrap --input-json "./amazon-review-output/amazon_<asin>_review_rows_translated.json" --output-dir "./amazon-review-output"
python scripts/amazon_review_workbook.py prepare-tagging --input-json "./amazon-review-output/amazon_<asin>_review_rows_translated.json" --output-dir "./amazon-review-output"
```

### 合并标注结果，导出最终工作簿

```bash
python scripts/amazon_review_workbook.py merge-build --base-json "./amazon-review-output/amazon_<asin>_review_rows_translated.json" --labels-json "./amazon-review-output/amazon_<asin>_labels.json" --output-dir "./amazon-review-output" --taxonomy-version "v1" --strict
```

## 关键词策略

现在的关键词搜索已经做了收束和提速：

- `deep` 模式默认只跑 combo，不自动跑关键词
- 只有显式传 `--keywords` 才会进入关键词阶段
- `--keywords` 不带值时，会使用内置 profile
- `--keyword-tier core` 只跑当前 profile 里更偏高收益的核心词
- `--keyword-tier explore` 只跑长尾探索词，并优先更贴近当前 profile 的尾词
- 不传 `--keyword-tier` 时默认是 `all`，兼容之前“整组 profile 一起跑”的行为
- `--time-budget-minutes 5` 可以把一次试跑限制在 5 分钟左右；到点后脚本会停止启动新的 combo / keyword / page，并保留已经抓到的结果
- `--combo-concurrency 2` 会在同一浏览器会话里并发开 2 个 combo tab，优先压缩总耗时；如果后续实测发现更高并发也稳定，再继续往上试
- 内置 profile：
  - `generic`
  - `electronics`
  - `dashcam`
- 默认复用策略是 `successful`
  - 历史上搜出过新增评论的关键词会被跳过
  - 近期 0 命中的关键词会临时抑制，避免短时间重复撞墙

示例：

```bash
python scripts/amazon_review_workbook.py intake --url "<amazon-url>" --output-dir "./amazon-review-output" --keywords --keyword-profile electronics
```

```bash
python scripts/amazon_review_workbook.py intake --url "<amazon-url>" --output-dir "./amazon-review-output" --keywords --keyword-profile electronics --keyword-tier core
```

```bash
python scripts/amazon_review_workbook.py intake --url "<amazon-url>" --output-dir "./amazon-review-output" --keywords --keyword-profile electronics --keyword-tier core --time-budget-minutes 5
```

```bash
python scripts/amazon_review_workbook.py intake --url "<amazon-url>" --output-dir "./amazon-review-output" --time-budget-minutes 5 --combo-concurrency 2
```

```bash
python scripts/amazon_review_workbook.py intake --url "<amazon-url>" --output-dir "./amazon-review-output" --keywords --keyword-profile dashcam --keyword-reuse-scope none
```

## 关键词自动调优

可以根据历史 SQLite 缓存和旧关键词实验报告，生成或刷新调优状态：

```bash
python scripts/amazon_review_workbook.py keyword-autotune --output-dir "./amazon-review-output" --db-path "./amazon-review-output/amazon_review_cache.sqlite3" --report-glob "./reports/*keywords*.json"
```

它会生成 `keyword_tuning_state.json`，之后关键词阶段会自动优先读取这个调优结果。

## 主要命令

- `doctor`
- `collect`
- `intake`
- `coverage-check`
- `keyword-autotune`
- `translate`
- `taxonomy-bootstrap`
- `prepare-tagging`
- `merge-build`
- `summary`

## 输出契约

事实工作簿和最终工作簿都使用固定 14 列：

1. `序号`
2. `评论用户名`
3. `国家`
4. `星级评分`
5. `评论原文`
6. `评论中文版`
7. `评论概括`
8. `情感倾向`
9. `类别分类`
10. `标签`
11. `重点标记`
12. `评论链接网址`
13. `评论时间`
14. `评论点赞数`

详细字段规则见 [references/output-schema.md](references/output-schema.md)。

## 测试

```bash
python -m unittest discover -s tests -p "test_*.py"
```

## 说明

- `.env`、SQLite 缓存、真实评论导出文件、本地输出产物默认都不会提交
- 这个仓库发布的是可复用 skill，不包含私有评论数据
