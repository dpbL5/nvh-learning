/**
 * QuestionRenderer: Shared utility for consistent question rendering across nvh_learning.
 * Automatically appends attached images to the bottom of the question stem.
 */
const QuestionRenderer = {
    /**
     * Renders the question stem/content.
     * @param {Object} q Question object from API
     * @param {Object} options Rendering options { showType: bool, showDiff: bool, containerClass: string }
     */
    renderStem(q, options = {}) {
        if (!q) return '';
        
        const imageMap = { ...(window.extractedImagesMap || {}), ...this._buildImageMap(q.question_images) };
        const text = (q.text || '').trim();
        const blocks = Array.isArray(q.content_json) ? q.content_json : [];
        
        let html = '';
        
        // 0. Render legacy image if exists
        if (q.image) {
            html += `<div class="text-center mb-3"><img src="${this._escapeHtml(q.image)}" class="img-fluid rounded border shadow-sm" style="max-height: 300px;" alt="Hình ảnh chính"></div>`;
        }
        
        // 1. Render blocks or text
        let contentHtml = '';
        if (blocks.length > 0) {
            contentHtml = this._renderBlocks(blocks, imageMap);
        } else if (text) {
            contentHtml = this._renderPlainWithImages(text, imageMap);
        }

        // 1.5 Special handling for true_false fields (question_text, context)
        if (q.question_type === 'true_false') {
            const qHeading = q.question_text ? `<div class="fw-bold mb-2 text-primary" style="font-size: 1.1rem;">${this._escapeHtml(q.question_text)}</div>` : '';
            const ctxBox = q.context ? `<div class="bg-light p-3 mb-3 rounded border-start border-4 border-secondary shadow-sm small fst-italic"><strong>Ngữ cảnh:</strong> ${this._escapeHtml(q.context)}</div>` : '';
            html += qHeading + ctxBox + contentHtml;
        } else {
            html += contentHtml;
        }
        
        // 2. Append unreferenced images at the bottom
        const unreferencedImages = this._getUnreferencedImages(q.question_images, text, blocks);
        if (unreferencedImages.length > 0) {
            html += '<div class="q-attached-images-wrap mt-3 d-flex flex-column gap-3">';
            unreferencedImages.forEach(img => {
                const url = img.image_url || img.image?.image_url;
                if (url) {
                    html += `<div class="text-center"><img src="${this._escapeHtml(url)}" class="img-fluid rounded border shadow-sm" style="max-height: 400px;" alt="Hình ảnh đính kèm"></div>`;
                }
            });
            html += '</div>';
        }
        
        return `<div class="q-renderer-stem ${options.containerClass || ''}">${html}</div>`;
    },

    /**
     * Renders an option (multiple choice or true/false statement).
     */
    renderOption(opt, questionImages = [], options = {}) {
        const imageMap = { ...(window.extractedImagesMap || {}), ...this._buildImageMap(questionImages) };
        const text = (opt.text || '').trim();
        const blocks = Array.isArray(opt.content_json) ? opt.content_json : [];
        
        if (blocks.length > 0) {
            return this._renderBlocks(blocks, imageMap);
        }
        return this._renderPlainInline(text, imageMap);
    },

    // --- Private Helpers ---

    _buildImageMap(qImages) {
        const map = {};
        if (Array.isArray(qImages)) {
            qImages.forEach(qi => {
                const sha = qi.image?.sha256;
                const url = qi.image_url || qi.image?.image_url;
                if (sha && url) {
                    map[sha] = url;
                }
            });
        }
        return map;
    },

    /**
     * Finds images in question_images that are NOT already manually placed in blocks or text.
     */
    _getUnreferencedImages(qImages, text, blocks) {
        if (!Array.isArray(qImages)) return [];
        
        // Build set of referenced SHAs
        const referencedShas = new Set();
        
        // From blocks
        blocks.forEach(b => {
            if (b.type === 'image' && b.sha256) referencedShas.add(b.sha256);
        });
        
        // From text (plain sha256 or markdown ![]())
        if (text) {
            qImages.forEach(qi => {
                const sha = qi.image?.sha256;
                if (sha && text.includes(sha)) {
                    referencedShas.add(sha);
                }
            });
        }
        
        // Return only unreferenced images (filter by placement if needed, but usually we want all stem images)
        // Here we include any image that isn't found in text/blocks
        return qImages.filter(qi => {
            const sha = qi.image?.sha256;
            const url = qi.image_url || qi.image?.image_url;
            return url && (!sha || !referencedShas.has(sha));
        });
    },

    _healBlocks(blocks, imageMap) {
        if (!Array.isArray(blocks)) return [];
        const newBlocks = [];
        const imgPattern = /\[IMG:([a-fA-F0-9]{32,64})\]/g;
        
        blocks.forEach(b => {
            if (b.type === 'text' && b.value) {
                const val = String(b.value);
                let lastEnd = 0;
                let match;
                while ((match = imgPattern.exec(val)) !== null) {
                    const start = match.index;
                    const end = imgPattern.lastIndex;
                    // Add preceding text
                    if (start > lastEnd) {
                        newBlocks.push({ type: 'text', value: val.substring(lastEnd, start) });
                    }
                    // Add image block
                    newBlocks.push({ type: 'image', sha256: match[1] });
                    lastEnd = end;
                }
                // Add remaining text
                if (lastEnd < val.length) {
                    newBlocks.push({ type: 'text', value: val.substring(lastEnd) });
                }
            } else {
                newBlocks.push(b);
            }
        });
        return newBlocks;
    },

    _renderBlocks(blocks, imageMap) {
        const healedBlocks = this._healBlocks(blocks, imageMap);
        return healedBlocks.map(b => {
            if (b.type === 'text') return `<span style="white-space: pre-wrap;">${this._escapeHtml(b.value)}</span>`;
            if (b.type === 'image') {
                const url = b.url || (b.sha256 ? imageMap[b.sha256] : null);
                if (url) {
                    return `<div class="text-center my-3"><img src="${this._escapeHtml(url)}" class="img-fluid rounded border shadow-sm" style="max-height: 400px;"></div>`;
                }
            }
            return '';
        }).join('');
    },

    _renderPlainWithImages(text, imageMap = {}) {
        if (!text) return '';
        const blocks = [{ type: 'text', value: text }];
        return this._renderBlocks(blocks, imageMap);
    },

    _renderPlainInline(text, imageMap = {}) {
        if (!text) return '';
        const blocks = [{ type: 'text', value: text }];
        const healedBlocks = this._healBlocks(blocks, imageMap);
        return healedBlocks.map(b => {
            if (b.type === 'text') return `<span>${this._escapeHtml(b.value)}</span>`;
            if (b.type === 'image') {
                const url = b.url || (b.sha256 ? imageMap[b.sha256] : null);
                if (url) {
                    return `<div class="text-center my-1"><img src="${this._escapeHtml(url)}" class="rounded border shadow-sm mx-1" style="max-height: 120px; width: auto;"></div>`;
                }
            }
            return '';
        }).join('');
    },

    extractTextFromBlocks(blocks) {
        if (!Array.isArray(blocks)) return '';
        return blocks
            .filter((b) => b && b.type === 'text' && typeof b.value === 'string')
            .map((b) => b.value)
            .join(' ')
            .replace(/\s+/g, ' ')
            .trim();
    },

    _escapeHtml(unsafe) {
        return (unsafe || '').toString()
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }
};

if (typeof window !== 'undefined') {
    window.QuestionRenderer = QuestionRenderer;
}
