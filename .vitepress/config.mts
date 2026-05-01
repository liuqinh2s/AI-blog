import { defineConfig } from "vitepress";
import fs from "fs";
import path from "path";

// 读取自动生成的侧边栏配置
function loadSidebar() {
    const sidebarPath = path.resolve(__dirname, "sidebar.json");
    if (fs.existsSync(sidebarPath)) {
        return JSON.parse(fs.readFileSync(sidebarPath, "utf-8"));
    }
    // 默认侧边栏
    return {
        "/posts/": [{ text: "博客文章", items: [] }],
        "/digests/": [
            { text: "日报", link: "/digests/daily/" },
            { text: "周刊", link: "/digests/weekly/" },
            { text: "月刊", link: "/digests/monthly/" },
            { text: "季刊", link: "/digests/quarterly/" },
            { text: "年刊", link: "/digests/yearly/" },
        ],
    };
}

export default defineConfig({
    title: "liuqinh2s' AI Blog",
    description: "Notion 随手记 → AI 总结 → 自动生成知识期刊",
    base: "/AI-blog/",
    lang: "zh-CN",
    cleanUrls: true,

    head: [
        ["meta", { name: "theme-color", content: "#5f67ee" }],
        ["link", { rel: "icon", href: "/AI-blog/favicon.ico", type: "image/x-icon" }],
    ],

    themeConfig: {
        nav: [
            { text: "首页", link: "/" },
            { text: "博客", link: "/posts/" },
            { text: "标签", link: "/tags/" },
            {
                text: "期刊",
                items: [
                    { text: "日报", link: "/digests/daily/" },
                    { text: "周刊", link: "/digests/weekly/" },
                    { text: "月刊", link: "/digests/monthly/" },
                    { text: "季刊", link: "/digests/quarterly/" },
                    { text: "年刊", link: "/digests/yearly/" },
                ],
            },
        ],

        sidebar: loadSidebar(),

        socialLinks: [
            { icon: "github", link: "https://github.com/liuqinh2s/AI-blog" },
        ],

        search: {
            provider: "local",
        },

        outline: {
            level: [2, 3],
            label: "目录",
        },

        lastUpdated: {
            text: "最后更新",
        },

        docFooter: {
            prev: "上一篇",
            next: "下一篇",
        },
    },
});
