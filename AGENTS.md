INSTRUCTIONS FOR LARGE LANGUAGE MODELS
=====================================

Overview
--------

*simplegallery* is a very old file/image gallery upload application, written in PHP and build on the Laravel web framework.  *simplegallery* itself is the replacement of an older web application written in PHP from scratch.

*simplegallery* is the application powering https://upload.sifnt.net.au/, providing a semi-anonymous file, image and video storage service for the sifnt.net.au website and user forum, providing very similar functionalily to the popular Imgur service, though it predates it.

*simplegallery* was last updated in July 2019 when it was dockerised and updated to Laravel 4.2 for easier deployment to newer servers but is no longer maintained.

It is planned that *simpleupload* be replaced with a new application written in Python and using modern web frameworks.

*pyupload*, this project, is to be the replacement for *simplegallery*.  It is intended that *pyupload* provides the same simple user interface and that it, at least initially, adopts the same underlying database and filesystem structure as *simplegallery* whilst providing the foundation for future improvements.


Instructions
------------

  1. Human first: Intended to be contributed by humans, with minimal editing by robots.
  2. LLM input and guidance is appreciated, but edits to code must only be made with explicitly granted permission.
  3. All test cases are maintained by an LLM, with tests updated at each commit.
  4. It is currently required that an LLM maintain the `TODO` file, including removing items that are no longer required, desired, or have been completed.
  5. When a code review is requested, the current feature status should be compared to `TODO.md` and the active implementation plan, if there is one.
  6. *simplegallery* may be referred to for feature and implementation details, but should not be considered as a reference for code quality or style.  *simplegallery* is found in the `simplegallery` directory of the parent directory of this project, and also on GitHub at https://github.com/samburney/simplegallery.git.


Python tooling
--------------

  1. Use `uv` for Python package management, to run pytest etc...
  2. Use the Python virtual environment at `.venv` for all Python development.


Documentation
-------------

### Implementation plans
  1. Individual implementation plans will be kept in `docs/plannings`, named `implement-<feature to implement>.md`.
  2. Feature implementations should usually happen in a branch matching the name or intent of the implementation plan.
  3. Implementation plans must have concise steps, with clear outcomes and acceptance criteria.
  4. They should not contain code snippets or examples unless critical to the implementation of the feature (For example, the formatting of a string or regex could be provided to ensure implementation compliance).
  5. When asked by the user to review the status of the codebase relative to an implementation plan perform the following:
    - Re-read related files, do not assume your cache or context is up to date.
    - Where a task has been implemented as defined in the implementation plan, simply mark the acceptance criteria as completed.
    - Where a task has been implemented in a way the differs from the exact wording of the implementation plan, but either meets or exceeds the feature's intended function, note this to the user and mark the acceptance criteria as completed.  In cases where this occurs, check if dependancies on this feature also need to be updated.  Make a note of this to the user but do not make any changes until confirmed to do so.
    - It is acceptable to make short notes about a task's implementation and deviations in the implementation plan during review.
    - Where a tasks's implementation significantly deviates from the intended function in the implementation plan do not mark it as complete.  Raise the deviation with the user, and provide feedback with recommendations on how to proceed.
    - Once completed, mark the tasks as done.
    - Once a step is completed, update the Overview section with current implemenation status.
  6. Unit tests must be implemented as each task progresses.  Adequate tests written and passing are considered an implicit acceptance criteria.  This will ensure future steps do not cause regressions in completed steps which may not be picked up due to tests not yet being completed.
  7. An implementation plan should follow the format as defined below:
    ```
    # Implementation Plan: [Feature Name]

    ## Overview
    [Blurb describing the goals of this implementation plan.]

    ### Scope
    - [Items in scope]
    - [Items in scope]
    ...

    ### Current State
    - [Current implementation state]
    - [Current implementation state]
    ...

    ### Target State
    - [Target state]
    - [Target state]
    - [Summary of remaining work to reach target state]
    - [Summary of remaining work to reach target state]
    ...

    ---

    ## Step 1: [Step Title]

    **Files**: [relevant files]

    **Tasks**:
    1. [ ] [Task]
    2. [ ] [Task]
    ...

    **Tests**
    1. [ ] [Test]
    2. [ ] [Test]
    ...

    **Acceptance Criteria**:
    - [ ] [Criterion]
    - [ ] [Criterion]
    ...

    **Implementation Notes**: [Optional]
    - Implementation notes go here, if detail is required to impolement particular features
    - This keeps the sections above concise and neat.
    ...

    **Dependencies**: [Optional]
    - List dependencies on other steps here
    - Multiple can be listed if required
    ...


    ---

    ## Step 2: [Step Title]

    **Files**: [relevant files]

    **Tasks**:
    1. [ ] [Task]
    2. [ ] [Task]
    ...

    **Tests**
    1. [ ] [Test]
    2. [ ] [Test]
    ...

    **Acceptance Criteria**:
    - [ ] [Criterion]
    - [ ] [Criterion]
    ...

    **Implementation Notes**: [Optional]
    - Implementation notes go here, if detail is required to impolement particular features
    - This keeps the sections above concise and neat.
    ...

    **Dependencies**: [Optional]
    - List dependencies on other steps here
    - Multiple can be listed if required
    ...

    ---

    ...
    ```

## Roadmap
  1. Contained in `TODO.md`
  2. Each feature mentioned in the roadmap must concise and not too specific.
  3. Each feature has a checkbox which must be empty until the feature is completed.  It is acceptable for features which are partially implemented to have a short comment against them stating this, and listing very briefly tasks required for the feature to be considered complete.
  4. The roadmap has fixes main sections:
    a) Current release: Contains features either implemenented in, or to be implemented in, the current release.
    b) Future release: Features out of scope for the current release and planned for the next release.
    c) Future enchancements: Planned features not yet scheduled to be implement in either the current or future release.
      - Future enhancements may contain collections of features under related subheadings.
    d) Potential future enhancements: A list of nice-to-have future features not currently planned for implementation.
    e) Fixes or minor enhancements: A list of known fixes or minor enhancements which may be implemented at any time.
  5. Where a feature mentioned in a section other than the current release is implemented, it's acceptable to move this feature to the current release list and mark it as completed.
  

Development database access
---------------------------

  1. The development database will usually be running locally in a docker container
  2. The details for the container should be found in `.env`, `docker-compose.yaml` and `docker-compose.override.yaml`
  3. An example database command might be:
    `docker compose exec db sh -c 'mariadb -u"${MYSQL_USER}" -p"${MYSQL_PASS}" -D"${MYSQL_DATABASE}"'`
  4. Database state can also be accessed using `uv run aerich inspectdb`
