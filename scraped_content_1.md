[![JSLegendDev’s Substack](https://substackcdn.com/image/fetch/$s_!bYsl!,w_80,h_80,c_fill,f_auto,q_auto:good,fl_progressive:steep,g_auto/https%3A%2F%2Fsubstack-post-media.s3.amazonaws.com%2Fpublic%2Fimages%2F6ffa63e4-c735-4985-8071-0c10cd1abfc6_250x250.png)](https://jslegenddev.substack.com/)

[JSLegendDev’s Substack](https://jslegenddev.substack.com/)

============================================================

SubscribeSign in

![User's avatar](https://jslegenddev.substack.com/p/fl_progressive:steep/https%3A%2F%2Fsubstack-post-media.s3.amazonaws.com%2Fpublic%2Fimages%2F146d4f55-ad77-459b-a94c-fe5922268673_250x250.png)

Discover more from JSLegendDev’s Substack

Articles and tutorials on web development, game development and the intersection of both.

Subscribe

By subscribing, I agree to Substack's [Terms of Use](https://substack.com/tos)
, and acknowledge its [Information Collection Notice](https://substack.com/ccpa#personal-data-collected)
 and [Privacy Policy](https://substack.com/privacy)
.

Already have an account? Sign in

How to Start Making Games in JavaScript with No Experience
==========================================================

[![JSLegendDev's avatar](https://jslegenddev.substack.com/p/fl_progressive:steep/https%3A%2F%2Fsubstack-post-media.s3.amazonaws.com%2Fpublic%2Fimages%2F146d4f55-ad77-459b-a94c-fe5922268673_250x250.png)](https://substack.com/@jslegenddev)

[JSLegendDev](https://substack.com/@jslegenddev)

Aug 19, 2025

2

[](https://jslegenddev.substack.com/p/how-to-start-making-games-in-javascript/comments)
[](javascript:void(0))

[![](https://jslegenddev.substack.com/p/fl_progressive:steep/https%3A%2F%2Fsubstack-post-media.s3.amazonaws.com%2Fpublic%2Fimages%2F62fa0097-a1b5-434b-bca1-1395ec91736e_1280x720.png)](https://substackcdn.com/image/fetch/$s_!oYkb!,f_auto,q_auto:good,fl_progressive:steep/https%3A%2F%2Fsubstack-post-media.s3.amazonaws.com%2Fpublic%2Fimages%2F62fa0097-a1b5-434b-bca1-1395ec91736e_1280x720.png)

It’s been a while since I started making web games in JavaScript. In this post, I’d like to share tips that would be helpful for beginners wanting to do the same.

Learn JavaScript Outside of Game Development Alongside HTML and CSS


=====================================================================

This might sound obvious, but I really recommend learning to program before learning game dev. For JavaScript, that means learning the fundamentals of the language and how it integrates with HTML and CSS.

Considering that JavaScript is primarily used on the web to make websites and web apps, I recommend that your first few projects be web related and not game related. Game development has a lot of domain specific knowledge to grasp. A beginner would easily be overwhelmed with having to learn programming, programming in JavaScript, HTML and CSS to make the web page on which the JavaScript will run and game development all at once.

You don’t have to learn everything in JavaScript either, just the core fundamentals. You’ll learn more obscure features during practice when building projects.

Learn That There are Two JavaScripts, The one That Runs in Node.js and The one That Runs on The Web


=====================================================================================================

For some time, JavaScript was relegated to a scripting language used for making web pages built using HTML and CSS, interactive. However, when the Node.js runtime was released, it allowed devs to run JavaScript outside of the browser on their machines, similarly to other languages like C#, Python, etc… This enabled JavaScript to be used for more than just websites.

There were now two major environments where JavaScript could run, in the browser and in Node.js.

When creating a server side or command line application, you would write JavasScript that would run directly on the user’s machine with Node.js. However, even for JavaScript that was intended to run on a web page, you would still use Node.js, not to run the code but to install tools useful for transforming your JavaScript before it runs on a web page.

This is due to an innovation that was brought with Node.js: The ability to download packages directly from a package manager called NPM (stands for Node Package Manager). The days where you needed to import a library by linking it using a script tag in your HTML were over.

These tools, called bundlers would bundle the libraries you installed via NPM alongside your JavaScript code and compile them into a single compact JavaScript file that you could run within a web page.

Developers would also write a more ergonomic version of JavaScript that had features not supported by browsers since they relied on the bundler to transpile whatever they wrote into JavaScript that was browser supported.

For example, React, arguably the most popular library for building web UIs, allows you to author UI components in an easy fashion by using an HTML-like syntax within your JavaScript called JSX. However, JSX is not valid in JavaScript. That’s why the bundler will transform your JavaScript code using JSX into JavaScript that doesn’t so it can run in the browser while retaining the same functionality. At the end of the day, what can be done with JSX can still be done in regular JS but in a more verbose way. That’s why we let the bundlers deal with it to make our lives easier.

All this to say, that today, most JavaScript developers, use a dev setup built around using Node.js and NPM even if the intended code is to run in the browser and not in Node.js.

For gamedev, that implies installing Node, using a build tool like Vite, installing your game frameworks/libraries via NPM, and compiling/transpiling your code to a version that can run on the web. This is often called “your build”. This build is what you deploy on your website or on platforms like itch.io.

You get a more streamlined experience from this setup since your Node.js based project keeps track of your libraries’ versions via a file called package.json (updating a library is one command away), you have access to hot reloading (meaning every time you modify your code, the change is immediately reflected which is a game changer for gamedev since this allows you to iterate quickly) and a local server is spun up automatically for you so that you can preview your project easily.

The old way of doing things is still available if you wish to avoid that complexity. For example, you can download the JavaScript file for the library, link it to you HTML using a script tag and finally install an extension like live server in VSCode to benefit from a local server and hot reloading. However, you’d still need to manually keep track of what version of the library you’re using and manually have to download new versions and replace the existing one in your project’s folder which can become tedious.

Stick to 2D, Since 3D is More Complicated


===========================================

While using JavaScript for 2D games is viable, for 3D, it’s a different story. It’s very hard to compete with modern engines like Unity and Unreal which are more suited for creating 3D games and abstract away a lot of the complexity that comes with 3D.

However, there are still 3D focused libraries like Three.js but there are more suited for 3D experiences that lives on a web page rather than full fledge games. I concede that it’s still possible to make a good looking 3D game if you’re able to come up with a unique art direction. As an idea you could try replicating the HD-2D artstyle of Square Enix. Putting 2D sprites into a low poly 3D world and add post processing effects.

Pick a Framework/Library


==========================

Games made in JavaScript are rendered within the HTML canvas element of a web page. By default, you have access to the canvas API allowing you to render graphics. For those unfamiliar, it’s similar to PyGame or Love2D where you have to basically write most things from scratch.

While this is very good for learning and you’ll learn knowledge that is transferable to other lower level game dev environment, I don’t think it’s the way to go for beginners.

At least, it depends on why you’re doing game dev. If you like the technical challenges that comes with making a game, using no libraries could be more fulfilling but unfortunately time consuming. However, if you care about results, meaning having finished games, it would be wiser to use a framework or a library that offers a lot out of the box. As a beginner you’ll be more likely to finish projects which will in turn increase your motivation and increase the likelihood that you stick with game dev long term.

However, as opposed to using an engine like Unity, Godot, Unreal, using a frameworks still allows to you architect your codebase with a greater degree of freedom and prevents you from spending too much time learning how specific game engine workflows and UIs work.

For JavaScript, I recommend going with [KAPLAY](https://kaplayjs.com/)
 due to it’s simplicity and intuitive API. [I have a video explaining the library in 5 minutes that you can watch next.](https://www.youtube.com/watch?v=JaEBkTsgXiQ)
 For something more established, [Phaser](https://phaser.io/)
 is the dominant player and is more performant even though it has a steeper learning curve.

Use a Map Editor like Tiled/LDTK


==================================

Manually placing objects in your game via code will get tedious quickly and make you wish you used a proper game engine. Fortunately, there is a solution. You can use a map editor like [Tiled](https://www.mapeditor.org/)
 or [LDTK](https://ldtk.io/)
 to create your game’s levels/maps visually like you would do in game engine.

I really recommend investing the time to learn how to use one.

Stick to One Tutorial, Start to Finish


========================================

When getting started, you might be tempted to follow a project based tutorial. There’s nothing wrong with that. Just stick with it from start to finish. Don’t hop between different tutorials. Doing this will only slow down your progress.

Once you have completed following along, you can start building an original project that heavily leverages what was taught in the tutorial. It’s at that stage that you actually learn. Before that, you’re only getting exposed to various concepts without them being consolidated in your mind.

Learn Pixel Art


=================

Your game will sooner or later need graphics. At first, there is nothing wrong with using ready made asset packs. However, I think it’s worth the investment to learn how to make good pixel art since you’ll be able to make the sprites you need without having be dependent on an asset pack existing for your particular use case.

A nice intermediate step between using asset packs and making your own sprites from scratch is to modifiy existing asset packs. This is actually very helpful in gradually developing an understanding of what makes good pixel art.

Learning to modify asset packs well, is also very useful when you need to use multiple ones for a single project as it will allow you to make everything look consistent.

In terms of software I use is Aseprite. It’s the most popular option. However, it doesn’t really matter what software you use as long as it works for you. You can check some of the pixel art I make on my [itch.io](https://jslegend.itch.io/)
 page.

Pixel art is an art form where you have the highest likelihood of making something that passes the professional quality bar in a reasonable amount of time. That’s why it’s my go-to art style.

[I recommend checking my pixel art for programmers video for more tips.](https://www.youtube.com/watch?v=Fgoj4nj9P8M)

Make Small Games First


========================

This is now the standard advice parroted online but by making small games, you’re more likely to finish a project. This will in turn motivate you to continue game development and increase your skills for the next project, so on and so forth.

If you lack ideas, try remaking existing simple games like pong, duck hunt, etc… I have tutorials on my channel you can follow.

Deploying Your Games


======================

I recommend publishing your games not only on your own website (if you have one) but on platform like itch.io where people interested in games congregate. For itch.io, you might find it hard to find players if you just upload your game. That’s why I recommend joining a game jam as you’ll be more likely to get feedback on your games that way.

Unfortunately, ways to successfully monetize web game development are rather limited. However you’re not limited to the web, you can transform your JavaScript web game into a desktop app that can be sold on Steam.

The simplest way I’ve found of achieving this was to use the NW.js technology which is similar to the more popular Electron but much simpler to use.

I have an exclusive step by step tutorial on Patreon teaching you how to make a downloadable desktop space shooter game with KAPLAY and NW.js for Mac, Windows and Linux.

[Check it out here!](https://www.patreon.com/posts/learn-to-build-136112954)

Conclusion


============

Hope these tips where useful in your JavaScript game development journey. If you’re interested in more content like this, consider subscribing to not miss out when I post something new.

Subscribe

[The KAPLAY Game Library in 5 Minutes\
------------------------------------](https://jslegenddev.substack.com/p/the-kaplay-game-library-in-5-minutes)

[JSLegendDev](https://substack.com/profile/173229486-jslegenddev)

·

Aug 2

[![The KAPLAY Game Library in 5 Minutes](https://jslegenddev.substack.com/p/g_auto/https%3A%2F%2Fsubstack-post-media.s3.amazonaws.com%2Fpublic%2Fimages%2F767276fd-c486-4e09-afce-3f886bbe6b94_1920x1080.png)](https://jslegenddev.substack.com/p/the-kaplay-game-library-in-5-minutes)

Hi, in this post, I’ll try to explain what is KAPLAY and what are its major concepts in 5 minutes. Let’s get started!

[Read full story](https://jslegenddev.substack.com/p/the-kaplay-game-library-in-5-minutes)

[![cristiano's avatar](https://jslegenddev.substack.com/p/fl_progressive:steep/https%3A%2F%2Fsubstack.com%2Fimg%2Favatars%2Fpurple.png)](https://substack.com/profile/1485790-cristiano)
[![Vikram Dutt's avatar](https://jslegenddev.substack.com/p/fl_progressive:steep/https%3A%2F%2Fbucketeer-e05bbc84-baa3-437e-9518-adb32be77984.s3.amazonaws.com%2Fpublic%2Fimages%2F667d48e0-2f91-4d7e-8a3b-667680518764_144x144.png)](https://substack.com/profile/2164636-vikram-dutt)

2 Likes

[](https://substack.com/note/p-170456472/restacks?utm_source=substack&utm_content=facepile-restacks)

2

[](https://jslegenddev.substack.com/p/how-to-start-making-games-in-javascript/comments)

[Share](javascript:void(0))

#### Discussion about this post

CommentsRestacks

![User's avatar](https://jslegenddev.substack.com/p/fl_progressive:steep/https%3A%2F%2Fsubstack.com%2Fimg%2Favatars%2Fdefault-light.png)

TopLatestDiscussions

[Why Use React for Game Development?](https://jslegenddev.substack.com/p/why-use-react-for-game-development)

[React.js is a “library” for making UIs.](https://jslegenddev.substack.com/p/why-use-react-for-game-development)

Oct 19, 2024 • [JSLegendDev](https://substack.com/@jslegenddev)

6

[](https://jslegenddev.substack.com/p/why-use-react-for-game-development/comments)
[](javascript:void(0))

![](https://substackcdn.com/image/fetch/$s_!DbZc!,w_320,h_213,c_fill,f_auto,q_auto:good,fl_progressive:steep,g_center/https%3A%2F%2Fsubstack-post-media.s3.amazonaws.com%2Fpublic%2Fimages%2F5cfeb866-d2f4-4334-9fa5-f3bffc709bd5_2626x1473.png)

[How to Implement Infinite Parallax Scrolling Backgrounds in JavaScript](https://jslegenddev.substack.com/p/how-to-implement-infinite-parallax)

[Using The Kaplay.js Game Library](https://jslegenddev.substack.com/p/how-to-implement-infinite-parallax)

Aug 16, 2024 • [JSLegendDev](https://substack.com/@jslegenddev)

11

[](https://jslegenddev.substack.com/p/how-to-implement-infinite-parallax/comments)
[](javascript:void(0))

![](https://substackcdn.com/image/fetch/$s_!cT5n!,w_320,h_213,c_fill,f_auto,q_auto:good,fl_progressive:steep,g_center/https%3A%2F%2Fsubstack-post-media.s3.amazonaws.com%2Fpublic%2Fimages%2F7feb4465-91ad-407f-9fb1-f9aea072aa21_1906x1065.png)

[How to use Tiled with Kaplay/Kaboom.js](https://jslegenddev.substack.com/p/how-to-use-tiled-with-kaboomjs)

[A guide on how to draw your levels in Tiled and render them in Kaboom.](https://jslegenddev.substack.com/p/how-to-use-tiled-with-kaboomjs)

May 11, 2024 • [JSLegendDev](https://substack.com/@jslegenddev)

8

[](https://jslegenddev.substack.com/p/how-to-use-tiled-with-kaboomjs/comments)
[](javascript:void(0))

![](https://substackcdn.com/image/fetch/$s_!0tkB!,w_320,h_213,c_fill,f_auto,q_auto:good,fl_progressive:steep,g_center/https%3A%2F%2Fsubstack-post-media.s3.amazonaws.com%2Fpublic%2Fimages%2F419dfa16-5124-4d5b-8a82-6e4f8a5cd1aa_1280x720.png)

See all

Ready for more?

Subscribe