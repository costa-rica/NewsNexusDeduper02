# News Nexus 09

- 2025-09-26

## Overview

Article collecting and analysis of news articles from various sources. The Consumer Product Safety Commission (CPSC) has hired Kinetic Metrics to collect articles on hazards caused by consumer products in the United States.

## Suite of Tools

### Core Platform

- Database: NewsNexusDb09 (TypeScript)
- SQLite, Sequelize
- API: NewsNexusApi09 (JavaScript)
- Web App: NewsNexusWeb09 (JavaScript)

### Collection Tools

- NewsNexusRequesterGoogleRss02 (JavaScript): This app calls the Google RSS feed api, returns articles, and stores them in the News Nexus database. There is no automation. This runs manually and is triggered from the server, by me Nick.
- NewsNexusRequesterNewsApi01 (JavaScript): Article collections, requests from https://newsapi.org/.
- NewsNexusRequesterNewsDataIo01 (JavaScript): Article collections, requests from https://newsdata.io.
- NewsNexusRequesterGNews02 (JavaScript): Article collections, requests from https://gnews.io.

### Analysis Tools

- NewsNexusDeduper02 (Python): Deduplication of articles.
- NewsNexusSemanticScorer02 (JavaScript): uses the Xenova/paraphrase-MiniLM-L6-v2 open source feature-extraction model from HuggingFace. This app, uses key words based on the solicitation requirements and placed into a .csv file to rate articles. The highest rated category for the article is stored as the Nexus Semantic Rating in the database. The rating is an indicator for how relevant the article is to the CPSC’s requirements. 0% is not related at all and 100% is very relevant. This application is run after each of the articles collection apps are run, triggered by the news article collection application using the child-process node.js package.
- NewsNexusClassifierLocationScorer01 (Python):is a Python application that uses the facebook/bart-large-mnli zero shot classification open source model from HuggingFace. This application is used to determine how likely the events of the article are to have occurred in the United States. A rating of 0% is unlikely and 100% is very likely to have occurred in the US. The application again stores the rating in the database.

## Production Environment

The News Nexus database is stored on the Ubuntu production sever that also houses all the platform applications. The Ubuntu server is actually a VMWare virtual machine that runs behind a reverse proxy server that is also a VMWare virtual machine.

All the applications are managed by PM2 on the server.

## Other References

- Consumer Product Safety Commission (CPSC) Statement of work: `CPSC___News_Clip_Collection_Project_.pdf`
