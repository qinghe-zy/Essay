# 发现记录

## 仓库概况
- 前端为 Vue 3 + Element Plus，页面集中在 `blog-frontend/src/views`，路由只包含 `Login.vue`、`Register.vue`、`Home.vue`、`BlogDetail.vue`、`UserCenter.vue`。
- 后端为 Spring Boot + MyBatis 注解式 Mapper，核心控制器有 `UserController`、`BlogController`、`ActionController`、`CommentController`、`NotificationController`、`AIController`、`FileController`。
- 数据表定义集中在 `blog_system.sql`，与本次 8 个模块直接相关的表主要是 `user`、`blog`、`visit_log`、`user_like`、`user_action`、`comment`、`notification`。

## 模块证据

### 1. 用户与资料管理
- 前端页面：`Login.vue` 调 `/api/user/login`；`Register.vue` 调 `/api/user/register`，头像上传走 `/api/upload`；`UserCenter.vue` 设置页调 `/api/user/update`，并再次使用 `/api/upload`。
- 后端链路：`UserController` 暴露 `/register`、`/login`、`/update`、`/stats`、`/profile-summary`、`/radar`；`UserService.register()` 做查重和 MD5；`UserMapper` 操作 `user` 表；`FileController` 上传文件，`WebConfig` 将 `/images/**` 映射到本地 `uploads/`。
- 涉及表：`user`；上传文件落本地目录，不落数据库独立文件表。

### 2. 博客发布 / 编辑 / 删除
- 前端页面：`Home.vue` 发布、搜索、删除；`BlogDetail.vue` 编辑；`UserCenter.vue` 的“文章管理”删除与查看。
- 后端链路：`BlogController` 暴露 `/all`、`/add`、`/search`、`/delete/{id}`、`/detail/{id}`、`/update`；`BlogService.saveBlog/updateBlog/deleteBlog/getBlogDetail`；`BlogMapper.insert/update/deleteById/findById/findAllWithFilter/searchWithFilter`。
- 涉及表：`blog`；详情访问时同时写 `visit_log`。

### 3. 阅读记录与时长
- 前端页面：`BlogDetail.vue` 进入详情后加载 `/api/blog/detail/{id}`，离开页面时通过 `sendBeacon` 调 `/api/blog/duration`；`UserCenter.vue` 展示 `/api/blog/history` 与 `/api/user/stats`。
- 后端链路：`BlogController.detail/history/duration`；`BlogService.getBlogDetail/getRecentBlogs`；`VisitLogMapper.insert/updateDuration/sumDurationByUserId/selectViewedTags/selectViewedTagDurationRecords`。
- 涉及表：`visit_log`，关联 `blog` 读取标签与历史文章。

### 4. 点赞 / 收藏 / 待读 / 拉黑
- 前端页面：`BlogDetail.vue` 有点赞、收藏、待读、不感兴趣四类动作；`UserCenter.vue` 书架页展示点赞、收藏、待读、黑名单，并支持取消/移除。
- 后端链路：点赞走 `BlogController.like/checkLike/my-likes` -> `BlogService.toggleLike` -> `BlogMapper` 的 `user_like` 与 `blog.likes` 更新；收藏/待读/拉黑走 `ActionController.toggle/check/list` -> `UserActionMapper`，收藏还会更新 `blog.collects`；拉黑同时被 `BlogMapper.findAllWithFilter/searchWithFilter/findHotBlogsWithFilter/findCollaborativeBlogs` 用于过滤。
- 涉及表：`user_like`、`user_action`、`blog`。

### 5. 评论与评分
- 前端页面：`BlogDetail.vue` 调 `/api/comment/list/{id}`、`/api/comment/add`、`/api/comment/delete/{id}`、`/api/comment/getScore`。
- 后端链路：`CommentController` 暴露上述接口；新增/删除实际委托给 `BlogService.addComment/deleteComment`；`CommentMapper` 负责插入、查询、删评、清理旧评分、读取用户评分；`BlogService.updateBlogAverageScore` 回写文章平均分。
- 涉及表：`comment`、`blog`。

### 6. 通知
- 前端页面：`UserCenter.vue` 的消息中心调 `/api/notification/list`、`/count`、`/read`、`/read-all`。
- 后端链路：`NotificationController` 直接调用 `NotificationMapper`；通知写入发生在 `BlogService.sendNotification()`，当前仅由点赞和评论触发。
- 涉及表：`notification`。

### 7. 推荐
- 前端页面：`Home.vue` 的“猜你喜欢”调 `/api/blog/recommend`；`Home.vue` 文章卡片展示 `recommendReason`；`BlogDetail.vue` 相关推荐调 `/api/blog/related/{id}`；`UserCenter.vue` 的画像摘要与雷达图调 `/api/user/profile-summary`、`/api/user/radar`。
- 后端链路：个性化推荐主入口是 `BlogController.recommend` -> `BlogService.getPersonalizedBlogs` -> `RecommendationEngine.recommend`。引擎组合 `CollaborativeRecallStrategy`、`TagRecallStrategy`、`HotRecallStrategy`、`AiRerankStrategy`、`DiversityRerankStrategy`。画像由 `RecommendationProfileServiceImpl.buildProfile` 基于 `VisitLogMapper.selectViewedTagDurationRecords/selectLikedTags/selectCollectedTags` 构建。相关推荐由 `BlogService.getRelatedBlogs` 调 `BlogMapper.findRelatedBlogs`。
- 涉及表：`visit_log`、`user_like`、`user_action`、`blog`。
- 反证：SQL 中虽存在 `recommendation` 表，但当前 Java / Vue 主链路未发现对该表的实际读写。

### 8. AI 摘要与标签生成
- 前端页面：`Home.vue` 发布弹窗中的“DeepSeek 一键生成摘要与标签”调用 `/api/ai/analyze`，把返回的 `summary` 与 `tags` 回填到发布表单。
- 后端链路：`AIController.analyze` -> `AIService.generateSummaryAndTags`，读取 `application.properties` 中的 `ai.deepseek.*` 配置，调用 DeepSeek 接口；失败时返回本地降级摘要和“系统暂无标签”。
- 涉及表：未发现直接写库；结果由前端用户确认后，随 `/api/blog/add` 写入 `blog.summary`、`blog.tags`。

## 边界结论
- `notification.type` 在 SQL 注释里写了 `3=收藏`，但当前代码只发现点赞(type=1)和评论(type=2)触发通知。
- `user_behavior`、`recommendation` 表在 SQL 中存在，但当前实现链路中未发现控制器/服务/Mapper 调用。
