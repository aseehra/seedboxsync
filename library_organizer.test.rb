# frozen_string_literal: true
# typed: strict

ENV["RACK_ENV"] = "test"

require "minitest/autorun"
require_relative("./library_organizer")

extend T::Sig # rubocop:disable Style/MixinUsage

describe "LibraryOrganizer" do
  describe "#parse_series" do
    it "parses normal sXXeXX formatted names" do
      path = Pathname.new("/home/arun/star.trek.strange.new.worlds.s01e02.mkv")
      result = LibraryOrganizer.new.series_name(path)
      assert_equal(Pathname.new("star trek strange new worlds"), result)
    end

    it "parses normal SSxEE formatted names" do
      path = Pathname.new("/home/arun/star.trek.strange.new.worlds.1x02.mkv")
      result = LibraryOrganizer.new.series_name(path)
      assert_equal(Pathname.new("star trek strange new worlds"), result)
    end
  end
end
