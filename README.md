## Documentation
[See Tournament Discord Bot commands](https://docs.google.com/document/d/1YAG8q635DSeRuDgBeu2qCAeQKf4nNzFANp_poy2CdbA/edit?usp=sharing)


## Authentication

Create an application, then a bot user and you can directly use the token of the bot user in your `config.py`:

```
BOT_IDENTITY = {
    'token' : 'changeme'
}
```

For further information about getting a bot user into a server please see: https://discordapp.com/developers/docs/topics/oauth2. You can use [this tool](https://discordapi.com/permissions.html) to generate a proper invitation link.


## Contributing

1. Fork it!
2. Create your feature branch: `git checkout -b my-new-feature`
3. Commit your changes: `git commit -am 'Add some feature'`
4. Push to the branch: `git push origin my-new-feature`
5. Submit a pull request :D
