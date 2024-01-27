# frozen_string_literal: true
# typed: strict

require "sorbet-runtime"
require "daemons"
require "logger"
require "rb-inotify"

extend T::Sig # rubocop:disable Style/MixinUsage

unless ENV["RACK_ENV"] == "test"
  Daemons.run_proc("library-organizer", { log_output: true }) do
  end
end

# Class
class LibraryOrganizer
  extend T::Sig

  sig { params(severity: Integer).void }
  def initialize(severity = Logger::Severity::DEBUG)
    @logger = T.let(Logger.new($stdout), Logger)
    @logger.level = severity
  end

  sig { params(path: Pathname).returns(T.nilable(Pathname)) }
  def series_name(path)
    normalized = path.basename.to_s.downcase

    series_name = case normalized
    when /(.*)\D(s\d+e\d+|\d+x\d+)/
      Regexp.last_match(1)&.gsub(".", " ")
    else
      @logger.warn("Could not parse series name: path=#{path}")
      return nil
    end

    @logger.debug("Parsed series name: path=#{path} series_name=#{series_name}")

    Pathname.new(series_name)
  end
end
