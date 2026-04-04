// ==UserScript==
// @name         NodeSeek Lucky Bot Pusher (No Local Storage)
// @namespace    http://tampermonkey.net/
// @version      7.0
// @description  自动检测 Lucky 链接并实时查询/推送到后端。
// @author       Yaya
// @match        https://www.nodeseek.com/post-*
// @grant        GM_xmlhttpRequest
// @run-at       document-end
// ==/UserScript==
(function() {
    'use strict';

    // ================= 配置区 =================
    // API_BASE_URL: 填写你的主项目地址（与 WEBHOOK_URL 一致，不含末尾斜杠）
    const API_BASE_URL = "https://your-domain.com";
    // AUTH_KEY: 与 .env 中的 LUCKY_AUTH_KEY 一致
    const AUTH_KEY = "your_lucky_auth_key_here";
    // =========================================

    const CUSTOM_BTN_CLASS = 'ns-lucky-record-btn';

    function findPublishButton() {
        const candidates = document.querySelectorAll('button, [role="button"]');
        for (let el of candidates) {
            const text = el.innerText.trim();
            if ((text === '发布' || text === '发布评论' || text === '只读') && !el.classList.contains(CUSTOM_BTN_CLASS)) {
                if (el.offsetParent !== null) return el;
            }
        }
        return null;
    }

    function setBtnState(btn, state) {
        btn.disabled = true;
        btn.style.cursor = "default";
        switch (state) {
            case 'saved':
                btn.innerText = "已保存";
                btn.style.borderColor = "#4caf50";
                btn.style.color = "#4caf50";
                break;
            case 'already_exists':
                btn.innerText = "已存在";
                btn.style.borderColor = "#2196f3";
                btn.style.color = "#2196f3";
                break;
            case 'error':
                btn.innerText = "请求失败";
                btn.style.borderColor = "#f44336";
                btn.style.color = "#f44336";
                btn.disabled = false;
                btn.style.cursor = "pointer";
                break;
            case 'loading':
                btn.innerText = "处理中...";
                break;
        }
    }

    function uploadToBot(luckyUrl, btn) {
        setBtnState(btn, 'loading');
        const title = document.title.replace(' - NodeSeek', '').trim();
        GM_xmlhttpRequest({
            method: "POST",
            url: `${API_BASE_URL}/lucky-webhook`,
            headers: {
                "Content-Type": "application/json",
                "x-auth-key": AUTH_KEY
            },
            data: JSON.stringify({ url: luckyUrl, title: title }),
            onload: function(response) {
                try {
                    const res = JSON.parse(response.responseText);
                    if (res.success) {
                        setBtnState(btn, res.message); // 'saved' 或 'already_exists'
                    } else {
                        setBtnState(btn, 'error');
                    }
                } catch (e) {
                    setBtnState(btn, 'error');
                }
            },
            onerror: function() {
                setBtnState(btn, 'error');
            }
        });
    }

    function inject() {
        const luckyLinks = document.querySelectorAll('a[href*="/lucky?post="]');
        if (luckyLinks.length === 0) return;

        const luckyUrl = luckyLinks[0].href;
        const publishBtn = findPublishButton();

        if (!publishBtn) return;
        const container = publishBtn.parentElement;
        if (container.querySelector(`.${CUSTOM_BTN_CLASS}`)) return;

        const myBtn = publishBtn.cloneNode(true);
        myBtn.classList.add(CUSTOM_BTN_CLASS);
        myBtn.innerText = "推送抽奖";
        myBtn.type = "button";
        myBtn.style.cssText = "margin-right: 10px !important; background-color: transparent !important; color: #ff9800 !important; border: 1px solid #ff9800 !important; min-width: auto !important; width: auto !important; padding: 0 15px !important; cursor: pointer !important; display: inline-flex !important; align-items: center !important; justify-content: center !important;";

        myBtn.onclick = (e) => {
            e.preventDefault();
            uploadToBot(luckyUrl, myBtn);
        };

        if (container.firstChild) {
            container.insertBefore(myBtn, container.firstChild);
        } else {
            container.appendChild(myBtn);
        }
    }

    inject();
    const observer = new MutationObserver(() => {
        if (!document.querySelector(`.${CUSTOM_BTN_CLASS}`)) inject();
    });
    observer.observe(document.body, { childList: true, subtree: true });
})();
