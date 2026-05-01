<script setup>
import { ref, computed } from 'vue'
import { useData } from 'vitepress'
import tagsData from '../tags.json'

const selectedTag = ref('')

const tags = computed(() => {
    const tagMap = {}
    for (const post of tagsData.posts) {
        for (const tag of post.tags) {
            if (!tagMap[tag]) {
                tagMap[tag] = []
            }
            tagMap[tag].push(post)
        }
    }
    return tagMap
})

const sortedTags = computed(() => {
    return Object.keys(tags.value).sort((a, b) => {
        return tags.value[b].length - tags.value[a].length
    })
})

const filteredPosts = computed(() => {
    if (!selectedTag.value) return []
    return tags.value[selectedTag.value] || []
})

function selectTag(tag) {
    selectedTag.value = selectedTag.value === tag ? '' : tag
}

function tagSize(count) {
    const min = 0.85
    const max = 1.6
    const maxCount = Math.max(...Object.values(tags.value).map(p => p.length))
    if (maxCount <= 1) return 1
    return min + (count / maxCount) * (max - min)
}
</script>

<template>
    <div class="tag-cloud-container">
        <div class="tag-cloud">
            <span
                v-for="tag in sortedTags"
                :key="tag"
                class="tag-item"
                :class="{ active: selectedTag === tag }"
                :style="{ fontSize: tagSize(tags[tag].length) + 'rem' }"
                @click="selectTag(tag)"
            >
                {{ tag }}
                <sup class="tag-count">{{ tags[tag].length }}</sup>
            </span>
        </div>

        <div v-if="selectedTag" class="tag-posts">
            <h2>
                🏷️ {{ selectedTag }}
                <span class="post-count">（{{ filteredPosts.length }} 篇）</span>
            </h2>
            <ul>
                <li v-for="post in filteredPosts" :key="post.link">
                    <a :href="post.link">
                        <span class="post-date">{{ post.date }}</span>
                        <span class="post-title">{{ post.title }}</span>
                    </a>
                </li>
            </ul>
        </div>

        <div v-else class="tag-hint">
            <p>👆 点击标签查看相关文章</p>
        </div>
    </div>
</template>

<style scoped>
.tag-cloud-container {
    margin-top: 1rem;
}

.tag-cloud {
    display: flex;
    flex-wrap: wrap;
    gap: 0.6rem 1rem;
    align-items: baseline;
    padding: 1.2rem;
    background: var(--vp-c-bg-soft);
    border-radius: 12px;
}

.tag-item {
    cursor: pointer;
    padding: 0.2rem 0.6rem;
    border-radius: 6px;
    color: var(--vp-c-text-2);
    transition: all 0.2s ease;
    white-space: nowrap;
}

.tag-item:hover {
    color: var(--vp-c-brand-1);
    background: var(--vp-c-brand-soft);
}

.tag-item.active {
    color: var(--vp-c-white);
    background: var(--vp-c-brand-1);
}

.tag-count {
    font-size: 0.7em;
    opacity: 0.6;
    margin-left: 2px;
}

.tag-posts {
    margin-top: 2rem;
}

.tag-posts h2 {
    border-bottom: none;
    margin-bottom: 1rem;
}

.post-count {
    font-size: 0.8em;
    color: var(--vp-c-text-3);
    font-weight: normal;
}

.tag-posts ul {
    list-style: none;
    padding: 0;
}

.tag-posts li {
    padding: 0.5rem 0;
    border-bottom: 1px solid var(--vp-c-divider);
}

.tag-posts li:last-child {
    border-bottom: none;
}

.tag-posts a {
    display: flex;
    gap: 1rem;
    align-items: baseline;
    text-decoration: none;
    color: var(--vp-c-text-1);
    transition: color 0.2s;
}

.tag-posts a:hover {
    color: var(--vp-c-brand-1);
}

.post-date {
    font-size: 0.85em;
    color: var(--vp-c-text-3);
    font-family: var(--vp-font-family-mono);
    flex-shrink: 0;
}

.post-title {
    font-weight: 500;
}

.tag-hint {
    margin-top: 2rem;
    text-align: center;
    color: var(--vp-c-text-3);
}
</style>
